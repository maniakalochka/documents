from typing import Any

from elasticsearch import AsyncElasticsearch, NotFoundError

from app.core.config import settings
from app.elastic.queries import build_search_query
from app.models.db_document import Document


class IncompleteSearchError(RuntimeError):
    """Elasticsearch returned only part of the matching documents."""


class ElasticDocumentRepository:
    PAGE_SIZE = 1_000
    PIT_KEEP_ALIVE = "1m"

    def __init__(
        self,
        client: AsyncElasticsearch,
        index_name: str | None = None,
    ) -> None:
        self.client = client
        self.index_name = index_name or settings.ELASTIC_INDEX

    async def get_matching_document_ids(self, query: str) -> list[int]:
        return await self.get_document_ids(build_search_query(query))

    async def get_document_ids(self, query: dict[str, Any]) -> list[int]:
        pit_response = await self.client.open_point_in_time(
            index=self.index_name,
            keep_alive=self.PIT_KEEP_ALIVE,
        )
        pit_id = pit_response["id"]

        document_ids: list[int] = []
        search_after: list[Any] | None = None

        try:
            while True:
                search_params: dict[str, Any] = {
                    "pit": {
                        "id": pit_id,
                        "keep_alive": self.PIT_KEEP_ALIVE,
                    },
                    "query": query,
                    "sort": ["_shard_doc"],
                    "size": self.PAGE_SIZE,
                    "source": False,
                    "track_total_hits": False,
                }

                if search_after is not None:
                    search_params["search_after"] = search_after

                response = await self.client.search(**search_params)

                pit_id = response.get("pit_id", pit_id)
                if response.get("timed_out") or response.get("_shards", {}).get("failed", 0):
                    raise IncompleteSearchError("Elasticsearch returned incomplete search results")

                hits = response["hits"]["hits"]

                if not hits:
                    break

                document_ids.extend(int(hit["_id"]) for hit in hits)
                search_after = hits[-1]["sort"]

            return document_ids

        finally:
            await self.client.close_point_in_time(id=pit_id)

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
                refresh="wait_for",
            )
        except NotFoundError:
            return
