from typing import Any

from elasticsearch import AsyncElasticsearch, BadRequestError, NotFoundError

from app.core.config import settings

DOCUMENTS_INDEX_MAPPING: dict[str, Any] = {
    "properties": {
        "id": {"type": "integer"},
        "text": {"type": "text"},
    }
}


async def create_index(
    client: AsyncElasticsearch,
    index_name: str | None = None,
) -> None:
    name = (index_name or settings.ELASTIC_INDEX).strip().lower()
    if not name:
        raise ValueError("ELASTIC_INDEX is empty")

    try:
        await client.indices.create(
            index=name,
            mappings=DOCUMENTS_INDEX_MAPPING,
        )
    except BadRequestError as e:
        error_type = None
        if isinstance(e.body, dict):
            error = e.body.get("error")
            if isinstance(error, dict):
                error_type = error.get("type")

        if error_type != "resource_already_exists_exception":
            raise


async def recreate_index(
    client: AsyncElasticsearch,
    index_name: str | None = None,
) -> None:
    name = (index_name or settings.ELASTIC_INDEX).strip().lower()
    if not name:
        raise ValueError("ELASTIC_INDEX is empty")

    try:
        await client.indices.delete(index=name)
    except NotFoundError:
        print(f"Index '{name}' does not exist, skipping deletion.")

    await client.indices.create(
        index=name,
        mappings=DOCUMENTS_INDEX_MAPPING,
    )
