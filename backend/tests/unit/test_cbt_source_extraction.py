"""Tests for deterministic CBT source-row extraction."""
from io import BytesIO

import pytest
from openpyxl import Workbook

from apps.cbt.services.source_extraction_service import (
    SourceExtractionError,
    extract_source_rows,
)


def test_csv_extraction_normalises_headers_and_preserves_source_row_numbers():
    content = (
        " Text , Correct , Option_A , Option_B\n"
        "What is 2+2?,B,3,4\n"
        ",,,\n"
        "What is 3+3?,B,5,6\n"
    ).encode()

    rows = extract_source_rows(content=content, source_format="csv")

    assert len(rows) == 2
    assert rows[0].sequence == 1
    assert rows[0].source_locator == {"row": 2}
    assert rows[1].sequence == 2
    assert rows[1].source_locator == {"row": 4}
    assert rows[0].payload == {
        "text": "What is 2+2?", "correct": "B", "option_a": "3", "option_b": "4"
    }
    assert len(rows[0].source_fingerprint) == 64
    assert rows[0].source_fingerprint != rows[1].source_fingerprint


def test_csv_extraction_rejects_duplicate_or_missing_required_headers():
    with pytest.raises(SourceExtractionError, match="duplicate"):
        extract_source_rows(
            content=b"text,Text,correct\nQuestion,Q,A\n", source_format="csv"
        )
    with pytest.raises(SourceExtractionError, match="missing required"):
        extract_source_rows(content=b"text,option_a\nQuestion,A\n", source_format="csv")


def test_csv_extraction_rejects_invalid_encoding_and_extra_data_columns():
    with pytest.raises(SourceExtractionError, match="UTF-8"):
        extract_source_rows(content=b"text,correct\n\xff,A\n", source_format="csv")
    with pytest.raises(SourceExtractionError, match="beyond the header"):
        extract_source_rows(content=b"text,correct\nQuestion,A,unexpected\n", source_format="csv")


def test_xlsx_extraction_preserves_sheet_and_native_cell_values():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Questions"
    sheet.append(["TEXT", "CORRECT", "OPTION_A", "OPTION_B", "MARKS"])
    sheet.append(["Which is even?", "B", "3", "4", 2])
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()

    rows = extract_source_rows(content=stream.getvalue(), source_format="xlsx")

    assert len(rows) == 1
    assert rows[0].source_locator == {"row": 2, "sheet": "Questions"}
    assert rows[0].payload["text"] == "Which is even?"
    assert rows[0].payload["marks"] == 2


def test_extraction_rejects_unsupported_format_and_empty_content():
    with pytest.raises(SourceExtractionError, match="only CSV and XLSX"):
        extract_source_rows(content=b"something", source_format="pdf")
    with pytest.raises(SourceExtractionError, match="empty"):
        extract_source_rows(content=b"", source_format="csv")
