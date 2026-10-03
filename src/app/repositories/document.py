from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_document import Document
from app.models.synchronization import pending_index_deletions


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def lock_synchronization(self) -> None:
        await self.session.execute(text("SELECT pg_advisory_xact_lock(84732)"))

    async def get_by_id(self, document_id: int) -> Document | None:
        statement = select(Document).where(Document.id == document_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_latest_by_ids(
        self,
        document_ids: list[int],
        limit: int = 20,
    ) -> list[Document]:
        candidates: list[Document] = []
        for start in range(0, len(document_ids), 10_000):
            statement = (
                select(Document)
                .where(Document.id.in_(document_ids[start : start + 10_000]))
                .order_by(Document.created_date.desc(), Document.id.desc())
                .limit(limit)
            )
            result = await self.session.execute(statement)
            candidates.extend(result.scalars().all())
        return sorted(
            candidates,
            key=lambda document: (document.created_date, document.id),
            reverse=True,
        )[:limit]

    async def has_pending_deletion(self, document_id: int) -> bool:
        result = await self.session.execute(
            select(pending_index_deletions.c.document_id).where(
                pending_index_deletions.c.document_id == document_id
            )
        )
        return result.scalar_one_or_none() is not None

    async def queue_index_deletion(self, document_id: int) -> None:
        await self.session.execute(
            insert(pending_index_deletions).values(document_id=document_id).on_conflict_do_nothing()
        )

    async def finish_index_deletion(self, document_id: int) -> None:
        await self.session.execute(
            delete(pending_index_deletions).where(
                pending_index_deletions.c.document_id == document_id
            )
        )

    async def delete(self, document: Document) -> None:
        await self.session.delete(document)

    async def commit(self) -> None:
        await self.session.commit()
