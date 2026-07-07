from elasticsearch import AsyncElasticsearch, NotFoundError

from app.core.config import settings
from app.elastic.queries import build_search_query
from app.models.db_document import Document


class ElasticDocumentRepository:
    def __init__(
        self,
        client: AsyncElasticsearch,
        index_name: str | None = None,
    ) -> None:
        self.client = client
        self.index_name = index_name or settings.ELASTIC_INDEX

    async def index_document(self, document: Document) -> None:
        await self.client.index(
            index=self.index_name,
            id=str(document.id),
            document={
                "id": document.id,
                "text": document.text,
            },
        )

    async def delete_document(self, document_id: int) -> None:
        try:
            await self.client.delete(
                index=self.index_name,
                id=str(document_id),
            )
        except NotFoundError:
            return

    async def search_document_ids(
        self,
        query: str,
        limit: int = 20,
    ) -> list[int]:
        response = await self.client.search(
            index=self.index_name,
            size=limit,
            query=build_search_query(query),
        )

        hits = response["hits"]["hits"]
        result: list[int] = []

        for hit in hits:
            source = hit.get("_source", {})
            document_id = source.get("id") or hit.get("_id")
            if document_id is not None:
                result.append(int(document_id))

        return result
