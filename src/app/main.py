from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from elastic_transport import TransportError
from elasticsearch import ApiError, AsyncElasticsearch
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.api.router import router
from app.core import get_logger
from app.core.config import settings
from app.database import engine
from app.elastic import create_elastic_client, create_index
from app.elastic.repository import IncompleteSearchError

logger = get_logger(__name__)


def create_app(
    database_engine: AsyncEngine | None = None,
    elastic_client: AsyncElasticsearch | None = None,
    index_name: str | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        database = database_engine if database_engine is not None else engine
        client = elastic_client if elastic_client is not None else create_elastic_client()
        application.state.engine = database
        application.state.session_factory = async_sessionmaker(database, expire_on_commit=False)
        application.state.elastic = client
        application.state.elastic_index = index_name or settings.ELASTIC_INDEX
        try:
            await create_index(client, application.state.elastic_index)
            yield
        finally:
            try:
                if elastic_client is None:
                    await client.close()
            finally:
                if database_engine is None:
                    await database.dispose()

    application = FastAPI(
        title="Document Search Service",
        version="1.0.0",
        description="Full-text search in Elasticsearch with documents stored in PostgreSQL.",
        lifespan=lifespan,
    )

    async def unavailable_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Storage operation failed: %s", type(exc).__name__)
        return JSONResponse(status_code=503, content={"detail": "Storage temporarily unavailable"})

    for exception_class in (TransportError, ApiError, SQLAlchemyError, IncompleteSearchError):
        application.add_exception_handler(exception_class, unavailable_handler)

    @application.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get(
        "/ready", tags=["health"], responses={503: {"description": "Storage unavailable"}}
    )
    async def ready(request: Request) -> dict[str, str]:
        async with request.app.state.session_factory() as session:
            await session.execute(text("SELECT 1"))
        await request.app.state.elastic.cluster.health(wait_for_status="yellow", timeout="5s")
        return {"status": "ready"}

    application.include_router(router)
    return application


app = create_app()
