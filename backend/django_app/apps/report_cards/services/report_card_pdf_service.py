"""Renders one ReportCard as an official, printable A4 PDF — the
authoritative document (§ the master prompt: "Do not generate the
official report card only on the frontend"). Built with ReportLab
Platypus (flowables laid out by a document template) rather than the
manual canvas.drawString positioning apps.finance/apps.reports use for
their simpler tabular exports — a multi-section report like this one
(header, student info, a variable-length subject table, attendance,
two comment blocks, signature lines) is what Platypus's automatic page
flow and Table/Paragraph flowables are for.
"""
import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..models import ReportCard

_STYLES = getSampleStyleSheet()
_TITLE = ParagraphStyle("RCTitle", parent=_STYLES["Title"], fontSize=16, spaceAfter=2)
_SUBTITLE = ParagraphStyle("RCSubtitle", parent=_STYLES["Normal"], fontSize=10, alignment=1)
_HEADING = ParagraphStyle(
    "RCHeading", parent=_STYLES["Heading3"], fontSize=11, spaceBefore=10, spaceAfter=4
)
_BODY = ParagraphStyle("RCBody", parent=_STYLES["Normal"], fontSize=9)
_CENTERED = ParagraphStyle("RCCentered", parent=_STYLES["Title"], fontSize=14, alignment=1)


def _school_header(school) -> list:
    flowables = [
        Paragraph(school.name.upper(), _CENTERED),
    ]
    contact_bits = [bit for bit in (school.address, school.phone, school.email) if bit]
    if contact_bits:
        flowables.append(Paragraph(" · ".join(contact_bits), _SUBTITLE))
    flowables.append(Spacer(1, 6))
    flowables.append(Paragraph("STUDENT ACADEMIC REPORT CARD", _SUBTITLE))
    flowables.append(Spacer(1, 4))
    flowables.append(HRFlowable(width="100%", thickness=1, color=colors.black))
    flowables.append(Spacer(1, 8))
    return flowables


def _student_info_table(report_card: ReportCard) -> Table:
    student = report_card.student
    rows = [
        ["Name:", f"{student.first_name} {student.last_name}", "Admission No:", student.admission_number],
        [
            "Class:",
            f"{report_card.class_level.name} {report_card.class_arm.name}",
            "Gender:",
            student.gender.title() if student.gender else "—",
        ],
        [
            "Academic Session:",
            report_card.academic_year.name,
            "Term:",
            report_card.term.name,
        ],
    ]
    table = Table(rows, colWidths=[3.2 * cm, 5.3 * cm, 3.2 * cm, 5.3 * cm])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _subjects_table(report_card: ReportCard) -> Table:
    header = ["Subject", "CA", "CBT", "Exam", "Total", "%", "Grade", "Remark"]
    rows = [header]
    for subject_row in report_card.subjects.select_related("subject").order_by("subject__name"):
        rows.append(
            [
                subject_row.subject.name,
                f"{subject_row.ca_score}/{subject_row.ca_max_score}",
                f"{subject_row.cbt_score}/{subject_row.cbt_max_score}",
                f"{subject_row.exam_score}/{subject_row.exam_max_score}",
                str(subject_row.total_score),
                f"{subject_row.percentage}%",
                subject_row.grade or "—",
                subject_row.remark or "—",
            ]
        )
    table = Table(
        rows,
        colWidths=[3.6 * cm, 1.8 * cm, 1.8 * cm, 1.8 * cm, 1.8 * cm, 1.6 * cm, 1.6 * cm, 3.4 * cm],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _overview_table(report_card: ReportCard) -> Table:
    position = (
        f"{report_card.class_position} of {report_card.class_size}"
        if report_card.class_position
        else "—"
    )
    rows = [
        ["Average", f"{report_card.average_percentage}%", "Position", position],
        [
            "School Days",
            str(report_card.attendance_present + report_card.attendance_absent),
            "Attendance",
            f"{report_card.attendance_percentage}%",
        ],
        ["Present", str(report_card.attendance_present), "Absent", str(report_card.attendance_absent)],
    ]
    table = Table(rows, colWidths=[3.2 * cm, 5.3 * cm, 3.2 * cm, 5.3 * cm])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _signature_block(label: str, comment: str, signer: str) -> list:
    return [
        Paragraph(f"<b>{label}</b>", _BODY),
        Paragraph(comment or "—", _BODY),
        Spacer(1, 14),
        HRFlowable(width="40%", thickness=0.75, color=colors.grey),
        Paragraph(f"{signer} signature", _BODY),
        Spacer(1, 6),
    ]


def render_report_card_pdf(report_card: ReportCard) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=f"Report Card {report_card.report_card_number}",
    )

    student = report_card.student
    school = student.school

    story: list = []
    story.extend(_school_header(school))

    # Student photo isn't embedded yet: apps.core.storage has no "read raw
    # bytes for a storage key" helper (only save_file/save_document/
    # get_presigned_download_url), and ReportLab's Image flowable needs
    # actual bytes, not a URL — adding that helper is a small, separate
    # change from "the PDF layout", left for a later pass.
    story.append(_student_info_table(report_card))
    story.append(Paragraph("ACADEMIC PERFORMANCE", _HEADING))
    story.append(_subjects_table(report_card))
    story.append(Paragraph("OVERALL PERFORMANCE & ATTENDANCE", _HEADING))
    story.append(_overview_table(report_card))

    story.append(Paragraph("COMMENTS", _HEADING))
    story.extend(_signature_block("Teacher's comment", report_card.teacher_comment, "Teacher"))
    story.extend(_signature_block("Principal's comment", report_card.principal_comment, "Principal"))

    story.append(Spacer(1, 10))
    next_term = (
        report_card.next_term_begins.strftime("%d %B %Y") if report_card.next_term_begins else "—"
    )
    story.append(Paragraph(f"<b>Next term begins:</b> {next_term}", _BODY))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"Report Card No: {report_card.report_card_number}", _BODY))

    doc.build(story)
    return buffer.getvalue()
