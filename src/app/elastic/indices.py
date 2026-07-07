from typing import Any

from elasticsearch import AsyncElasticsearch

from app.core.config import settings

DOCUMENTS_INDEX_MAPPING: dict[str, Any] = {
    "mappings": {
        "properties": {
            "id": {"type": "integer"},
            "text": {"type": "text"},
        }
    }
}


async def create_index(
    client: AsyncElasticsearch,
    index_name: str | None = None,
) -> None:
    name = index_name or settings.ELASTIC_INDEX

    exists = await client.indices.exists(index=name)
    if exists:
        return

    await client.indices.create(index=name, **DOCUMENTS_INDEX_MAPPING)


async def recreate_index(
    client: AsyncElasticsearch,
    index_name: str | None = None,
) -> None:
    name = index_name or settings.ELASTIC_INDEX

    exists = await client.indices.exists(index=name)
    if exists:
        await client.indices.delete(index=name)

    await client.indices.create(index=name, **DOCUMENTS_INDEX_MAPPING)
