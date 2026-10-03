import json
from pathlib import Path

from app.main import app


def test_docs_json_matches_current_openapi_schema() -> None:
    documentation = Path(__file__).resolve().parents[2] / "docs.json"
    assert json.loads(documentation.read_text(encoding="utf-8")) == app.openapi()
