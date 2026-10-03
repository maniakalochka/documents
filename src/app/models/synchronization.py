from sqlalchemy import Column, DateTime, Integer, String, Table, func

from app.database.base import Base

import_batches = Table(
    "import_batches",
    Base.metadata,
    Column("checksum", String(64), primary_key=True),
    Column("created_date", DateTime, nullable=False, server_default=func.now()),
)

pending_index_deletions = Table(
    "pending_index_deletions",
    Base.metadata,
    Column("document_id", Integer, primary_key=True),
)
