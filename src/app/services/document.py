from app.elastic.repository import ElasticDocumentRepository
from app.models.db_document import Document
from app.repositories.document import DocumentRepository


class DocumentService:
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
    ) -> list[Document]:
        document_ids = await self.elastic_repository.get_matching_document_ids(
            query=query,
        )

        if not document_ids:
            return []

        return await self.document_repository.get_latest_by_ids(
            document_ids,
            limit=20,
        )

    async def delete(self, document_id: int) -> bool:
        await self.document_repository.lock_synchronization()
        document = await self.document_repository.get_by_id(document_id)
        pending = await self.document_repository.has_pending_deletion(document_id)

        if document is not None:
            await self.document_repository.delete(document)
            await self.document_repository.queue_index_deletion(document_id)
            await self.document_repository.commit()
        await self.elastic_repository.delete_document(document_id)
        if document is not None or pending:
            await self.document_repository.finish_index_deletion(document_id)
            await self.document_repository.commit()
            return True

        return False
