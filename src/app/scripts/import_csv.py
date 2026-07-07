import argparse
import ast
import asyncio
import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, engine
from app.elastic import (
    ElasticDocumentRepository,
    close_elastic_client,
    create_elastic_client,
    create_index,
)
from app.models.db_document import Document


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
        for row in reader:
            documents.append(parse_csv_row(row))

    return documents


def to_document_model(parsed: ParsedDocument) -> Document:
    return Document(
        text=parsed.text,
        created_date=parsed.created_date,
        rubrics=parsed.rubrics,
    )


async def save_document(
    session: AsyncSession,
    elastic_repository: ElasticDocumentRepository,
    parsed_document: ParsedDocument,
) -> None:
    document = to_document_model(parsed_document)

    session.add(document)
    await session.flush()
    await elastic_repository.index_document(document)


async def import_csv(path: str | Path) -> None:
    parsed_documents = read_documents_from_csv(path)

    elastic_client = create_elastic_client()
    elastic_repository = ElasticDocumentRepository(elastic_client)

    await create_index(elastic_client)

    try:
        async with AsyncSessionLocal() as session:
            for parsed_document in parsed_documents:
                await save_document(
                    session=session,
                    elastic_repository=elastic_repository,
                    parsed_document=parsed_document,
                )

            await session.commit()
    except Exception:
        raise
    finally:
        await close_elastic_client(elastic_client)
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
