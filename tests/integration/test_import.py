from pathlib import Path
from unittest.mock import patch

import pytest
from elastic_transport import ConnectionError as ElasticConnectionError
from elasticsearch import AsyncElasticsearch
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.elastic.repository import ElasticDocumentRepository
from app.models.db_document import Document
from app.models.synchronization import import_batches
from app.repositories.document import DocumentRepository
from app.scripts.import_csv import import_csv, synchronize_index
from app.services.document import DocumentService


def write_csv(path: Path) -> None:
    path.write_text(
        "text,created_date,rubrics\n"
        "Mercedes,2025-01-01 12:00:00,\"['cars']\"\n"
        'Bicycle,2025-01-02 12:00:00,"[]"\n',
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_import_is_idempotent_and_does_not_resurrect_deleted_documents(
    tmp_path: Path,
    test_session: AsyncSession,
    test_engine: AsyncEngine,
    elastic_client: AsyncElasticsearch,
    test_index: str,
) -> None:
    path = tmp_path / "documents.csv"
    write_csv(path)
    sessions = async_sessionmaker(test_engine, expire_on_commit=False)
    await import_csv(path, sessions, elastic_client, test_index)
    original_ids = list(
        (await test_session.scalars(select(Document.id).order_by(Document.id))).all()
    )
    await test_session.rollback()
    await import_csv(path, sessions, elastic_client, test_index)
    assert (
        list((await test_session.scalars(select(Document.id).order_by(Document.id))).all())
        == original_ids
    )
    await test_session.rollback()
    assert (await elastic_client.count(index=test_index))["count"] == 2

    async with sessions() as session:
        service = DocumentService(
            DocumentRepository(session), ElasticDocumentRepository(elastic_client, test_index)
        )
        assert await service.delete(original_ids[0])
    await import_csv(path, sessions, elastic_client, test_index)
    assert await test_session.scalar(select(func.count()).select_from(Document)) == 1
    assert (await elastic_client.count(index=test_index))["count"] == 1


@pytest.mark.asyncio
async def test_failed_indexing_can_be_repaired_without_duplicate_database_records(
    tmp_path: Path,
    test_session: AsyncSession,
    test_engine: AsyncEngine,
    elastic_client: AsyncElasticsearch,
    test_index: str,
) -> None:
    path = tmp_path / "documents.csv"
    write_csv(path)
    sessions = async_sessionmaker(test_engine, expire_on_commit=False)
    with patch(
        "app.scripts.import_csv.index_documents_to_elastic",
        side_effect=ElasticConnectionError("unavailable"),
    ):
        with pytest.raises(ElasticConnectionError):
            await import_csv(path, sessions, elastic_client, test_index)
    assert await test_session.scalar(select(func.count()).select_from(Document)) == 2
    assert await test_session.scalar(select(func.count()).select_from(import_batches)) == 1
    await test_session.rollback()
    await import_csv(path, sessions, elastic_client, test_index)
    assert await test_session.scalar(select(func.count()).select_from(Document)) == 2
    assert (await elastic_client.count(index=test_index))["count"] == 2
    await test_session.rollback()

    await elastic_client.index(
        index=test_index, id="999999", document={"id": 999999, "text": "orphan"}, refresh=True
    )
    await synchronize_index(sessions, ElasticDocumentRepository(elastic_client, test_index))
    assert not bool(await elastic_client.exists(index=test_index, id="999999"))


@pytest.mark.asyncio
async def test_invalid_csv_does_not_write_documents_or_import_marker(
    tmp_path: Path,
    test_session: AsyncSession,
    test_engine: AsyncEngine,
    elastic_client: AsyncElasticsearch,
    test_index: str,
) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("text,created_date,rubrics\nMercedes,not-a-date,[]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="line 2"):
        await import_csv(path, async_sessionmaker(test_engine), elastic_client, test_index)
    assert await test_session.scalar(select(func.count()).select_from(Document)) == 0
    assert await test_session.scalar(select(func.count()).select_from(import_batches)) == 0
