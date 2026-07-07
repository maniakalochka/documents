from datetime import datetime

import pytest

from app.scripts.import_csv import (
    ParsedDocument,
    parse_created_date,
    parse_csv_row,
    parse_rubrics,
)


def test_parse_rubrics_returns_list_of_strings() -> None:
    raw = "['VK-1603736028819866', 'VK-11879320040', 'VK-63192684938']"

    result = parse_rubrics(raw)

    assert result == [
        "VK-1603736028819866",
        "VK-11879320040",
        "VK-63192684938",
    ]


def test_parse_rubrics_returns_empty_list() -> None:
    raw = "[]"

    result = parse_rubrics(raw)

    assert result == []


def test_parse_rubrics_raises_if_value_is_not_a_list() -> None:
    raw = "'not-a-list'"

    with pytest.raises(ValueError, match="rubrics must be a list"):
        parse_rubrics(raw)


def test_parse_rubrics_raises_if_list_contains_non_string() -> None:
    raw = "['VK-1', 123]"

    with pytest.raises(ValueError, match="each rubric must be a string"):
        parse_rubrics(raw)


def test_parse_created_date_returns_datetime() -> None:
    raw = "2019-07-25 12:42:13"

    result = parse_created_date(raw)

    assert result == datetime(2019, 7, 25, 12, 42, 13)


def test_parse_created_date_raises_on_invalid_format() -> None:
    raw = "25-07-2019"

    with pytest.raises(ValueError):
        parse_created_date(raw)


def test_parse_csv_row_returns_parsed_document() -> None:
    row = {
        "text": "  test text  ",
        "created_date": "2019-07-25 12:42:13",
        "rubrics": "['VK-1', 'VK-2']",
    }

    result = parse_csv_row(row)

    assert isinstance(result, ParsedDocument)
    assert result.text == "test text"
    assert result.created_date == datetime(2019, 7, 25, 12, 42, 13)
    assert result.rubrics == ["VK-1", "VK-2"]
