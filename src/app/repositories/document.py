from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_document import Document


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, document_id: int) -> Document | None:
        statement = select(Document).where(Document.id == document_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_ids(self, document_ids: list[int]) -> list[Document]:
        if not document_ids:
            return []

        statement = select(Document).where(Document.id.in_(document_ids))
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def delete(self, document: Document) -> None:
        await self.session.delete(document)

    async def commit(self) -> None:
        await self.session.commit()
