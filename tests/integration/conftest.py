import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from elasticsearch import AsyncElasticsearch
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.repositories.document import DocumentRepository

TEST_DATABASE_NAME = "documents_test"
TRUNCATE_DOCUMENTS = (
    "TRUNCATE TABLE documents, import_batches, pending_index_deletions RESTART IDENTITY"
)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestDatabaseSettings(BaseSettings):
    database_url: str | None = Field(default=None, validation_alias="TEST_DATABASE_URL")
    elastic_url: str = Field(default="http://localhost:9201", validation_alias="TEST_ELASTIC_URL")

    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")


def get_test_database_url() -> str:
    database_url = TestDatabaseSettings().database_url

    if not database_url:
        raise RuntimeError("Set TEST_DATABASE_URL in .env to the isolated documents_test database")

    if make_url(database_url).database != TEST_DATABASE_NAME:
        raise RuntimeError(
            f"TEST_DATABASE_URL must point to database '{TEST_DATABASE_NAME}' to run tests safely"
        )

    return database_url


@pytest.fixture(scope="session")
def migrated_test_database() -> None:
    database_url = get_test_database_url()
    migration_environment = {**os.environ, "DB_URL": database_url}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=PROJECT_ROOT,
        env=migration_environment,
        check=True,
    )


@pytest_asyncio.fixture
async def test_engine(migrated_test_database: None) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(get_test_database_url())

    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with test_engine.connect() as connection:
        await connection.execute(text(TRUNCATE_DOCUMENTS))
        await connection.commit()

        session = AsyncSession(bind=connection, expire_on_commit=False)

        try:
            yield session
        finally:
            await session.close()
            await connection.rollback()
            await connection.execute(text(TRUNCATE_DOCUMENTS))
            await connection.commit()


@pytest.fixture
def document_repository(test_session: AsyncSession) -> DocumentRepository:
    return DocumentRepository(test_session)


@pytest.fixture
def test_index() -> str:
    return f"documents-test-{uuid4().hex}"


@pytest_asyncio.fixture
async def elastic_client(test_index: str) -> AsyncIterator[AsyncElasticsearch]:
    client = AsyncElasticsearch(TestDatabaseSettings().elastic_url)
    try:
        yield client
    finally:
        try:
            await client.options(ignore_status=404).indices.delete(index=test_index)
        finally:
            await client.close()
