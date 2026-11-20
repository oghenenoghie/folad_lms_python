"""Unit coverage for the .xlsx parsing path — the API-level bulk-import
tests (tests/api/test_students_crud.py, test_staff_crud.py) only exercise
.csv uploads, so this covers the openpyxl branch directly.
"""
import io

import pytest
from openpyxl import Workbook

from apps.staff.services import bulk_import_service as staff_bulk_import
from apps.students.services import bulk_import_service as student_bulk_import


def _xlsx_bytes(header: list[str], rows: list[list]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(header)
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_student_bulk_import_parses_xlsx_rows():
    content = _xlsx_bytes(
        ["school_code", "first_name", "last_name", "date_of_birth"],
        [["BULK1", "Ada", "Okafor", "2012-03-04"], ["BULK1", "Femi", "Adeyemi", "2013-01-01"]],
    )

    rows = student_bulk_import.parse_rows(filename="roster.xlsx", content=content)

    assert len(rows) == 2
    assert rows[0]["first_name"] == "Ada"
    assert rows[1]["last_name"] == "Adeyemi"


def test_student_bulk_import_xlsx_skips_fully_blank_rows():
    content = _xlsx_bytes(
        ["school_code", "first_name", "last_name", "date_of_birth"],
        [["BULK1", "Ada", "Okafor", "2012-03-04"], [None, None, None, None]],
    )

    rows = student_bulk_import.parse_rows(filename="roster.xlsx", content=content)

    assert len(rows) == 1


def test_staff_bulk_import_parses_xlsx_rows():
    content = _xlsx_bytes(
        ["school_code", "first_name", "last_name", "position", "date_joined"],
        [["SBULK1", "Sam", "Smith", "Registrar", "2020-01-01"]],
    )

    rows = staff_bulk_import.parse_rows(filename="staff.xlsx", content=content)

    assert len(rows) == 1
    assert rows[0]["position"] == "Registrar"


@pytest.mark.parametrize(
    "row, expected_missing",
    [
        ({}, "school_code, first_name, last_name, date_of_birth"),
        ({"school_code": "X", "first_name": "A", "last_name": "B"}, "date_of_birth"),
    ],
)
def test_student_bulk_import_reports_missing_columns_by_name(row, expected_missing):
    with pytest.raises(student_bulk_import.BulkImportError, match=expected_missing):
        student_bulk_import._import_one_row(organization=None, actor=None, row=row)
