from unittest.mock import AsyncMock

import pytest

from app.elastic import ElasticDocumentRepository
from app.repositories.document import DocumentRepository


@pytest.fixture
def document_repository() -> AsyncMock:
    repository = AsyncMock(spec=DocumentRepository)
    repository.has_pending_deletion.return_value = False
    return repository


@pytest.fixture
def elastic_repository() -> AsyncMock:
    return AsyncMock(spec=ElasticDocumentRepository)
