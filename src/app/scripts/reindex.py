import asyncio

from app.database import AsyncSessionLocal, engine
from app.elastic import ElasticDocumentRepository, create_elastic_client
from app.scripts.import_csv import synchronize_index


async def main() -> None:
    client = create_elastic_client()
    try:
        await synchronize_index(AsyncSessionLocal, ElasticDocumentRepository(client))
    finally:
        try:
            await client.close()
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
