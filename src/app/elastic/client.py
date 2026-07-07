from elasticsearch import AsyncElasticsearch

from app.core.config import settings


def create_elastic_client() -> AsyncElasticsearch:
    return AsyncElasticsearch(
        hosts=[settings.ELASTIC_URL],
        request_timeout=30,
    )


async def close_elastic_client(client: AsyncElasticsearch) -> None:
    await client.close()
