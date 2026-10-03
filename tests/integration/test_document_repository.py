from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_document import Document
from app.repositories.document import DocumentRepository


@pytest.mark.asyncio
async def test_get_latest_by_ids_returns_twenty_latest_documents_in_stable_order(
    document_repository: DocumentRepository,
    test_session: AsyncSession,
) -> None:
    base_date = datetime(2026, 1, 1, 12, 0, 0)
    documents = [
        Document(
            text=f"Document {position}",
            rubrics=["test"],
            created_date=base_date + timedelta(days=position // 2),
        )
        for position in range(25)
    ]
    test_session.add_all(documents)
    await test_session.flush()

    document_ids = [document.id for document in documents]
    result = await document_repository.get_latest_by_ids(document_ids, limit=20)

    expected_documents = sorted(
        documents,
        key=lambda document: (document.created_date, document.id),
        reverse=True,
    )[:20]

    assert [document.id for document in result] == [document.id for document in expected_documents]
    assert len(result) == 20
    assert all(document.id in document_ids for document in result)


@pytest.mark.asyncio
async def test_get_latest_by_ids_returns_empty_list_for_empty_or_unknown_ids(
    document_repository: DocumentRepository,
) -> None:
    assert await document_repository.get_latest_by_ids([]) == []
    assert await document_repository.get_latest_by_ids([999_999]) == []
