from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.dependencies import get_async_session
from app.elastic.repository import ElasticDocumentRepository
from app.repositories.document import DocumentRepository
from app.services.document import DocumentService


async def get_document_repository(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> DocumentRepository:
    return DocumentRepository(session)


async def get_elastic_repository(request: Request) -> ElasticDocumentRepository:
    return ElasticDocumentRepository(request.app.state.elastic, request.app.state.elastic_index)


async def get_document_service(
    document_repository: DocumentRepository = Depends(get_document_repository),
    elastic_repository: ElasticDocumentRepository = Depends(get_elastic_repository),
) -> DocumentService:
    return DocumentService(
        document_repository=document_repository,
        elastic_repository=elastic_repository,
    )
