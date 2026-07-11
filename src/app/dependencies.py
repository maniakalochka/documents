from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.dependencies import get_async_session
from app.elastic.client import create_elastic_client
from app.elastic.repository import ElasticDocumentRepository
from app.repositories.document import DocumentRepository
from app.services.document import DocumentService


async def get_document_repository(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> DocumentRepository:
    return DocumentRepository(session)


async def get_elastic_repository() -> AsyncGenerator[ElasticDocumentRepository]:
    client = create_elastic_client()
    try:
        yield ElasticDocumentRepository(client)
    finally:
        await client.close()


async def get_document_service(
    document_repository: DocumentRepository = Depends(get_document_repository),
    elastic_repository: ElasticDocumentRepository = Depends(get_elastic_repository),
) -> DocumentService:
    return DocumentService(
        document_repository=document_repository,
        elastic_repository=elastic_repository,
    )
