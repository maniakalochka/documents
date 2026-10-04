from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
import pytest_asyncio
from elastic_transport import ConnectionError as ElasticConnectionError
from elasticsearch import AsyncElasticsearch
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.elastic.repository import ElasticDocumentRepository
from app.main import create_app
from app.models.db_document import Document
from app.models.synchronization import pending_index_deletions
from app.scripts.import_csv import index_documents_to_elastic


@pytest_asyncio.fixture
async def api_client(
    test_session: AsyncSession,
    test_engine: AsyncEngine,
    elastic_client: AsyncElasticsearch,
    test_index: str,
) -> AsyncIterator[AsyncClient]:
    application = create_app(test_engine, elastic_client, test_index)
    async with application.router.lifespan_context(application):
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://test"
        ) as client:
            yield client


@pytest.mark.asyncio
async def test_search_returns_twenty_newest_matching_documents_and_all_fields(
    api_client: AsyncClient,
    test_session: AsyncSession,
    elastic_client: AsyncElasticsearch,
    test_index: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ElasticDocumentRepository, "PAGE_SIZE", 7)
    documents = [
        Document(
            text="Mercedes sedan",
            rubrics=["cars"],
            created_date=datetime(2025, 1, 1) + timedelta(days=position // 2),
        )
        for position in range(25)
    ]
    unrelated = Document(text="Bicycle", rubrics=[], created_date=datetime(2030, 1, 1))
    test_session.add_all([*documents, unrelated])
    await test_session.commit()
    repository = ElasticDocumentRepository(elastic_client, test_index)
    repository.PAGE_SIZE = 7
    await index_documents_to_elastic(repository, [*documents, unrelated])
    await elastic_client.indices.refresh(index=test_index)

    response = await api_client.get("/documents/search", params={"q": "Mercedes"})
    assert response.status_code == 200
    expected = sorted(documents, key=lambda doc: (doc.created_date, doc.id), reverse=True)[:20]
    assert [row["id"] for row in response.json()] == [document.id for document in expected]
    assert all(set(row) == {"id", "text", "rubrics", "created_date"} for row in response.json())
    assert (await api_client.get("/documents/search", params={"q": "absentword"})).json() == []
    assert (await api_client.get("/documents/search", params={"q": ""})).status_code == 422
    whitespace_query = await api_client.get("/documents/search", params={"q": "   "})
    assert whitespace_query.status_code == 422
    assert whitespace_query.json() == {"detail": "Query must contain non-whitespace characters"}
    assert (await api_client.get("/ready")).status_code == 200


@pytest.mark.asyncio
async def test_delete_retries_after_elasticsearch_failure_and_cleans_both_stores(
    api_client: AsyncClient,
    test_session: AsyncSession,
    elastic_client: AsyncElasticsearch,
    test_index: str,
) -> None:
    document = Document(text="Mercedes", rubrics=[], created_date=datetime(2025, 1, 1))
    test_session.add(document)
    await test_session.commit()
    repository = ElasticDocumentRepository(elastic_client, test_index)
    await repository.index_document(document)
    await elastic_client.indices.refresh(index=test_index)
    with patch.object(elastic_client, "delete", side_effect=ElasticConnectionError("unavailable")):
        assert (await api_client.delete(f"/documents/{document.id}")).status_code == 503

    assert await test_session.scalar(select(Document.id).where(Document.id == document.id)) is None
    assert await test_session.scalar(select(pending_index_deletions.c.document_id)) == document.id
    assert bool(await elastic_client.exists(index=test_index, id=str(document.id)))

    assert (await api_client.delete(f"/documents/{document.id}")).status_code == 204
    assert not bool(await elastic_client.exists(index=test_index, id=str(document.id)))
    assert await test_session.scalar(select(pending_index_deletions.c.document_id)) is None
    assert (await api_client.delete(f"/documents/{document.id}")).status_code == 404
    assert (await api_client.get("/documents/search", params={"q": "Mercedes"})).json() == []
