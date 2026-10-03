from datetime import datetime
from typing import cast
from unittest.mock import AsyncMock

import pytest

from app.elastic.repository import ElasticDocumentRepository
from app.models.db_document import Document
from app.repositories.document import DocumentRepository
from app.services.document import DocumentService


@pytest.mark.asyncio
async def test_service_can_search_last_20_documents(
    document_repository: AsyncMock,
    elastic_repository: AsyncMock,
) -> None:
    elastic_repository.get_matching_document_ids.return_value = [15, 42, 7]

    expected_documents = [
        Document(
            id=42,
            text="Sample document text",
            rubrics=["cars"],
            created_date=datetime(2026, 10, 3, 12, 0, 0),
        ),
        Document(
            id=15,
            text="Another document text",
            rubrics=["cars"],
            created_date=datetime(2026, 10, 2, 12, 0, 0),
        ),
    ]

    document_repository.get_latest_by_ids.return_value = expected_documents

    service = DocumentService(
        document_repository=cast(DocumentRepository, document_repository),
        elastic_repository=cast(ElasticDocumentRepository, elastic_repository),
    )

    result = await service.search("Mercedes")

    assert result == expected_documents

    elastic_repository.get_matching_document_ids.assert_awaited_once_with(query="Mercedes")
    document_repository.get_latest_by_ids.assert_awaited_once_with([15, 42, 7], limit=20)


@pytest.mark.asyncio
async def test_search_returns_empty_list_without_database_query_when_no_ids_found(
    document_repository: AsyncMock,
    elastic_repository: AsyncMock,
) -> None:
    elastic_repository.get_matching_document_ids.return_value = []

    service = DocumentService(
        document_repository=cast(DocumentRepository, document_repository),
        elastic_repository=cast(ElasticDocumentRepository, elastic_repository),
    )

    result = await service.search("unknown phrase")

    assert result == []

    elastic_repository.get_matching_document_ids.assert_awaited_once_with(
        query="unknown phrase",
    )
    document_repository.get_latest_by_ids.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_returns_false_when_document_does_not_exist(
    document_repository: AsyncMock,
    elastic_repository: AsyncMock,
) -> None:
    document_repository.get_by_id.return_value = None

    service = DocumentService(
        document_repository=cast(DocumentRepository, document_repository),
        elastic_repository=cast(ElasticDocumentRepository, elastic_repository),
    )

    result = await service.delete(404)

    assert result is False

    document_repository.get_by_id.assert_awaited_once_with(404)
    document_repository.delete.assert_not_awaited()
    document_repository.commit.assert_not_awaited()
    elastic_repository.delete_document.assert_awaited_once_with(404)


@pytest.mark.asyncio
async def test_delete_removes_existing_document_from_database_and_index(
    document_repository: AsyncMock,
    elastic_repository: AsyncMock,
) -> None:
    document = Document(
        id=7,
        text="Document to delete",
        rubrics=["test"],
        created_date=datetime(2026, 10, 3, 12, 0, 0),
    )
    document_repository.get_by_id.return_value = document

    service = DocumentService(
        document_repository=cast(DocumentRepository, document_repository),
        elastic_repository=cast(ElasticDocumentRepository, elastic_repository),
    )

    result = await service.delete(7)

    assert result is True

    document_repository.get_by_id.assert_awaited_once_with(7)
    document_repository.delete.assert_awaited_once_with(document)
    assert document_repository.commit.await_count == 2
    document_repository.queue_index_deletion.assert_awaited_once_with(7)
    document_repository.finish_index_deletion.assert_awaited_once_with(7)
    elastic_repository.delete_document.assert_awaited_once_with(7)


@pytest.mark.asyncio
async def test_delete_retries_pending_deletion_without_redeleting_database_record(
    document_repository: AsyncMock,
    elastic_repository: AsyncMock,
) -> None:
    document_repository.get_by_id.return_value = None
    document_repository.has_pending_deletion.return_value = True
    service = DocumentService(
        cast(DocumentRepository, document_repository),
        cast(ElasticDocumentRepository, elastic_repository),
    )
    assert await service.delete(7) is True
    document_repository.delete.assert_not_awaited()
    elastic_repository.delete_document.assert_awaited_once_with(7)
    document_repository.finish_index_deletion.assert_awaited_once_with(7)
