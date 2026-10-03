import argparse
import ast
import asyncio
import csv
import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk
from sqlalchemy import delete, func, insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import get_logger
from app.database import AsyncSessionLocal, engine
from app.elastic import (
    ElasticDocumentRepository,
    close_elastic_client,
    create_elastic_client,
    create_index,
)
from app.models.db_document import Document
from app.models.synchronization import import_batches, pending_index_deletions

logger = get_logger(__name__)
SYNCHRONIZATION_LOCK = 84732


@dataclass(slots=True)
class ParsedDocument:
    text: str
    created_date: datetime
    rubrics: list[str]


def parse_rubrics(raw: str) -> list[str]:
    value = ast.literal_eval(raw)

    if not isinstance(value, list):
        raise ValueError("rubrics must be a list")

    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError("each rubric must be a string")
        result.append(item)

    return result


def parse_created_date(raw: str) -> datetime:
    return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")


def parse_csv_row(row: dict[str, str]) -> ParsedDocument:
    return ParsedDocument(
        text=row["text"].strip(),
        created_date=parse_created_date(row["created_date"]),
        rubrics=parse_rubrics(row["rubrics"]),
    )


def read_documents_from_csv(path: str | Path) -> list[ParsedDocument]:
    csv_path = Path(path)
    documents: list[ParsedDocument] = []

    with csv_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        required_columns = {"text", "created_date", "rubrics"}
        if not required_columns.issubset(reader.fieldnames or []):
            raise ValueError("CSV must contain text, created_date and rubrics columns")
        for row in reader:
            try:
                documents.append(parse_csv_row(row))
            except (KeyError, ValueError, SyntaxError, AttributeError, TypeError) as exc:
                raise ValueError(
                    f"Invalid CSV record ending at line {reader.line_num}: {exc}"
                ) from exc

    return documents


def to_document_model(parsed: ParsedDocument) -> Document:
    return Document(
        text=parsed.text,
        created_date=parsed.created_date,
        rubrics=parsed.rubrics,
    )


async def save_documents_to_postgres(
    session: AsyncSession,
    parsed_documents: list[ParsedDocument],
) -> list[Document]:
    documents: list[Document] = []

    for parsed_document in parsed_documents:
        document = to_document_model(parsed_document)
        session.add(document)
        documents.append(document)

    await session.flush()
    return documents


async def index_documents_to_elastic(
    elastic_repository: ElasticDocumentRepository,
    documents: list[Document],
) -> None:
    await async_bulk(
        elastic_repository.client,
        (
            {
                "_index": elastic_repository.index_name,
                "_id": str(document.id),
                "_source": {"id": document.id, "text": document.text},
            }
            for document in documents
        ),
        chunk_size=500,
    )


async def synchronize_index(
    session_factory: async_sessionmaker[AsyncSession],
    elastic_repository: ElasticDocumentRepository,
) -> None:
    """Repair the index from PostgreSQL; safe to retry after a partially failed bulk request."""
    await create_index(elastic_repository.client, elastic_repository.index_name)
    async with session_factory() as session:
        await session.execute(
            text("SELECT pg_advisory_xact_lock(:key)"), {"key": SYNCHRONIZATION_LOCK}
        )
        result = await session.execute(select(Document))
        documents = list(result.scalars().all())
        await elastic_repository.client.indices.refresh(index=elastic_repository.index_name)
        existing_ids = await elastic_repository.get_document_ids({"match_all": {}})
        document_ids = {document.id for document in documents}
        await index_documents_to_elastic(elastic_repository, documents)
        stale_ids = set(existing_ids) - document_ids
        if stale_ids:
            await async_bulk(
                elastic_repository.client,
                (
                    {
                        "_op_type": "delete",
                        "_index": elastic_repository.index_name,
                        "_id": str(doc_id),
                    }
                    for doc_id in stale_ids
                ),
                ignore_status=(404,),
            )
        await elastic_repository.client.indices.refresh(index=elastic_repository.index_name)
        await session.execute(delete(pending_index_deletions))
        await session.commit()
        logger.info(
            "Index synchronized: %s documents, %s stale IDs removed", len(documents), len(stale_ids)
        )


async def import_csv(
    path: str | Path,
    session_factory: async_sessionmaker[AsyncSession] = AsyncSessionLocal,
    elastic_client: AsyncElasticsearch | None = None,
    index_name: str | None = None,
) -> None:
    client = elastic_client if elastic_client is not None else create_elastic_client()
    try:
        parsed_documents = await asyncio.to_thread(read_documents_from_csv, path)
        file_content = await asyncio.to_thread(Path(path).read_bytes)
        checksum = hashlib.sha256(file_content).hexdigest()
        async with session_factory() as session:
            await session.execute(
                text("SELECT pg_advisory_xact_lock(:key)"), {"key": SYNCHRONIZATION_LOCK}
            )
            imported = await session.scalar(
                select(import_batches.c.checksum).where(import_batches.c.checksum == checksum)
            )
            if imported is None:
                has_batches = await session.scalar(select(func.count()).select_from(import_batches))
                has_documents = await session.scalar(select(func.count()).select_from(Document))
                if not has_batches and has_documents:
                    raise RuntimeError(
                        "Database contains documents from an untracked import. "
                        "Use reindex to preserve them, or import into a fresh database."
                    )
                await save_documents_to_postgres(session, parsed_documents)
                await session.execute(insert(import_batches).values(checksum=checksum))
                await session.commit()
                logger.info("CSV imported: %s documents", len(parsed_documents))
            else:
                logger.info("CSV already imported; repairing index without adding documents")
        await synchronize_index(session_factory, ElasticDocumentRepository(client, index_name))
    finally:
        try:
            if elastic_client is None:
                await close_elastic_client(client)
        finally:
            if session_factory is AsyncSessionLocal:
                await engine.dispose()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import documents from CSV into PostgreSQL and Elasticsearch",
    )
    parser.add_argument(
        "path",
        type=str,
        help="Path to CSV file",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    await import_csv(args.path)


if __name__ == "__main__":
    asyncio.run(main())
