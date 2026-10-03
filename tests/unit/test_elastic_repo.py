from unittest.mock import AsyncMock, call

import pytest

from app.elastic.repository import ElasticDocumentRepository


@pytest.mark.asyncio
async def test_get_matching_document_ids_reads_all_pages_and_closes_pit() -> None:
    client = AsyncMock()

    client.open_point_in_time.return_value = {
        "id": "pit-1",
    }

    client.search.side_effect = [
        {
            "pit_id": "pit-2",
            "hits": {
                "hits": [
                    {"_id": "10", "sort": [100]},
                    {"_id": "20", "sort": [200]},
                ],
            },
        },
        {
            "hits": {
                "hits": [
                    {"_id": "30", "sort": [300]},
                ],
            },
        },
        {
            "hits": {
                "hits": [],
            },
        },
    ]

    repository = ElasticDocumentRepository(
        client=client,
        index_name="documents",
    )

    result = await repository.get_matching_document_ids("Mercedes")

    assert result == [10, 20, 30]

    client.open_point_in_time.assert_awaited_once_with(
        index="documents",
        keep_alive="1m",
    )

    assert client.search.await_args_list == [
        call(
            pit={
                "id": "pit-1",
                "keep_alive": "1m",
            },
            query={
                "match": {
                    "text": {
                        "query": "Mercedes",
                    },
                },
            },
            sort=["_shard_doc"],
            size=1_000,
            source=False,
            track_total_hits=False,
        ),
        call(
            pit={
                "id": "pit-2",
                "keep_alive": "1m",
            },
            query={
                "match": {
                    "text": {
                        "query": "Mercedes",
                    },
                },
            },
            sort=["_shard_doc"],
            size=1_000,
            source=False,
            track_total_hits=False,
            search_after=[200],
        ),
        call(
            pit={
                "id": "pit-2",
                "keep_alive": "1m",
            },
            query={
                "match": {
                    "text": {
                        "query": "Mercedes",
                    },
                },
            },
            sort=["_shard_doc"],
            size=1_000,
            source=False,
            track_total_hits=False,
            search_after=[300],
        ),
    ]

    client.close_point_in_time.assert_awaited_once_with(id="pit-2")


@pytest.mark.asyncio
async def test_get_matching_document_ids_returns_empty_list_when_nothing_matches() -> None:
    client = AsyncMock()

    client.open_point_in_time.return_value = {
        "id": "pit-1",
    }
    client.search.return_value = {
        "hits": {
            "hits": [],
        },
    }

    repository = ElasticDocumentRepository(
        client=client,
        index_name="documents",
    )

    result = await repository.get_matching_document_ids("missing text")

    assert result == []

    client.close_point_in_time.assert_awaited_once_with(id="pit-1")


@pytest.mark.asyncio
async def test_get_matching_document_ids_closes_pit_when_search_fails() -> None:
    client = AsyncMock()

    client.open_point_in_time.return_value = {
        "id": "pit-1",
    }
    client.search.side_effect = ConnectionError("Elasticsearch is unavailable")

    repository = ElasticDocumentRepository(
        client=client,
        index_name="documents",
    )

    with pytest.raises(ConnectionError, match="Elasticsearch is unavailable"):
        await repository.get_matching_document_ids("Mercedes")

    client.close_point_in_time.assert_awaited_once_with(id="pit-1")
