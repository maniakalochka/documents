from app.elastic.repository import ElasticDocumentRepository
from app.models.db_document import Document
from app.repositories.document import DocumentRepository


class SearchService:
    def __init__(
        self,
        document_repository: DocumentRepository,
        elastic_repository: ElasticDocumentRepository,
    ) -> None:
        self.document_repository = document_repository
        self.elastic_repository = elastic_repository

    async def search(
        self,
        query: str,
        limit: int = 20,
    ) -> list[Document]:
        document_ids = await self.elastic_repository.search_document_ids(
            query=query,
            limit=limit,
        )

        if not document_ids:
            return []

        documents = await self.document_repository.get_by_ids(document_ids)

        documents.sort(
            key=lambda document: document.created_date,
            reverse=True,
        )

        return documents[:limit]
