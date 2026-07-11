from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import router
from app.core import get_logger
from app.database import AsyncSessionLocal, engine
from app.elastic import create_elastic_client, create_index

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting up...")
    app.state.engine = engine
    app.state.session_factory = AsyncSessionLocal
    elastic_client = create_elastic_client()
    await create_index(elastic_client)
    app.state.elastic = elastic_client

    try:
        yield
    finally:
        await elastic_client.close()


app = FastAPI(lifespan=lifespan)

app.include_router(router)
