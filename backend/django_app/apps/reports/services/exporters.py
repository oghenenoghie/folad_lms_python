"""The one place (title, headers, rows) becomes actual file bytes — three
formats, not three-times-N report-type functions. Cell values are cast to
`str` uniformly since callers mix strings, Decimals, and ints in the same
row (see generators.py) and none of csv/openpyxl/reportlab need to care
about the original Python type.
"""
import csv
import io

CONTENT_TYPES = {
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}


def export_table(*, title: str, headers: list[str], rows: list[list], fmt: str) -> bytes:
    if fmt == "csv":
        return _to_csv(headers, rows)
    if fmt == "xlsx":
        return _to_xlsx(title, headers, rows)
    if fmt == "pdf":
        return _to_pdf(title, headers, rows)
    raise ValueError(f"unsupported export format: {fmt!r}")


def _to_csv(headers: list[str], rows: list[list]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([str(value) for value in row])
    return buffer.getvalue().encode("utf-8")


def _to_xlsx(title: str, headers: list[str], rows: list[list]) -> bytes:
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = title[:31]  # Excel's own sheet-name length limit
    sheet.append(headers)
    for row in rows:
        sheet.append([str(value) for value in row])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _to_pdf(title: str, headers: list[str], rows: list[list]) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    column_width = (width - 80) / max(len(headers), 1)

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(40, height - 50, title)

    y = height - 85
    pdf.setFont("Helvetica-Bold", 9)
    for i, header in enumerate(headers):
        pdf.drawString(40 + i * column_width, y, str(header))
    pdf.setFont("Helvetica", 9)
    y -= 16

    for row in rows:
        if y < 50:
            pdf.showPage()
            pdf.setFont("Helvetica", 9)
            y = height - 50
        for i, value in enumerate(row):
            pdf.drawString(40 + i * column_width, y, str(value))
        y -= 14

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
