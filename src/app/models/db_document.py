from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Document(Base):
    __tablename__ = "documents"

    rubrics: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
