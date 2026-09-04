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
from datetime import date

from django.conf import settings
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from apps.core.storage import get_file_bytes
from apps.examinations.models import GradeBand, GradingScheme

from ..models import PSYCHOMOTOR_RATING_LABELS, ReportCard

_STYLES = getSampleStyleSheet()
_TITLE = ParagraphStyle("RCTitle", parent=_STYLES["Title"], fontSize=16, spaceAfter=2)
_SUBTITLE = ParagraphStyle("RCSubtitle", parent=_STYLES["Normal"], fontSize=10, alignment=1)
_HEADING = ParagraphStyle(
    "RCHeading", parent=_STYLES["Heading3"], fontSize=11, spaceBefore=10, spaceAfter=4
)
_BODY = ParagraphStyle("RCBody", parent=_STYLES["Normal"], fontSize=9)
_CENTERED = ParagraphStyle("RCCentered", parent=_STYLES["Title"], fontSize=14, alignment=1)


def _student_photo(student, *, width: float = 2.5 * cm, height: float = 3 * cm) -> Image | None:
    """None whenever there's no photo, or the stored one can't be read/
    decoded — a report card renders fine without it (see the photo's own
    column in _school_header just going blank), and this shouldn't be
    the reason a whole render fails."""
    if not student.photo_storage_key:
        return None
    photo_bytes = get_file_bytes(student.photo_storage_key)
    if not photo_bytes:
        return None
    try:
        return Image(io.BytesIO(photo_bytes), width=width, height=height)
    except Exception:
        return None


def _school_header(school, photo: Image | None) -> list:
    title_stack = [Paragraph(school.name.upper(), _CENTERED)]
    contact_bits = [bit for bit in (school.address, school.phone, school.email) if bit]
    if contact_bits:
        title_stack.append(Paragraph(" · ".join(contact_bits), _SUBTITLE))
    title_stack.append(Spacer(1, 6))
    title_stack.append(Paragraph("STUDENT ACADEMIC REPORT CARD", _SUBTITLE))

    if photo is not None:
        # colWidths sum to 18cm — exactly this doc's content width (A4's
        # 21cm minus the 1.5cm margin on each side), so the photo column
        # never has to compete with the title stack for space.
        header_row = Table([[title_stack, photo]], colWidths=[15 * cm, 3 * cm])
        header_row.setStyle(
            TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (1, 0), (1, 0), "RIGHT")])
        )
        flowables = [header_row]
    else:
        flowables = title_stack

    flowables.append(Spacer(1, 4))
    flowables.append(HRFlowable(width="100%", thickness=1, color=colors.black))
    flowables.append(Spacer(1, 8))
    return flowables


def _age(dob, *, as_of: date) -> str:
    if not dob:
        return "—"
    years = as_of.year - dob.year - ((as_of.month, as_of.day) < (dob.month, dob.day))
    return f"{years} yrs"


def _student_info_table(report_card: ReportCard) -> Table:
    student = report_card.student
    as_of = (report_card.generated_at.date() if report_card.generated_at else date.today())
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
        ["Age:", _age(student.date_of_birth, as_of=as_of), "No. in Class:", str(report_card.class_size or "—")],
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
    header = ["Subject", "CA", "CBT", "Exam", "Total", "%", "Class Avg", "Grade", "Remark"]
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
                f"{subject_row.class_average}%" if subject_row.class_average is not None else "—",
                subject_row.grade or "—",
                subject_row.remark or "—",
            ]
        )
    table = Table(
        rows,
        colWidths=[3.2 * cm, 1.5 * cm, 1.5 * cm, 1.5 * cm, 1.5 * cm, 1.3 * cm, 1.7 * cm, 1.3 * cm, 3.9 * cm],
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
        ["Overall Grade", report_card.overall_grade or "—", "Overall Remark", report_card.overall_remark or "—"],
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


def _psychomotor_table(report_card: ReportCard) -> Table | None:
    """None when the school hasn't rated this term yet (e.g. a report just
    generated and not yet reviewed by a teacher) — the section header this
    accompanies is skipped too rather than printing an empty table."""
    ratings = list(
        report_card.psychomotor_ratings.select_related("trait").order_by("trait__order", "trait__name")
    )
    if not ratings:
        return None

    # Two traits per row keeps this compact — a school's checklist can run
    # to 8+ traits, and one-per-row would push the affective domain onto
    # its own extra page for no real benefit.
    header = ["Trait", "Rating", "Trait", "Rating"]
    rows = [header]
    pairs = list(ratings)
    for i in range(0, len(pairs), 2):
        left = pairs[i]
        right = pairs[i + 1] if i + 1 < len(pairs) else None
        rows.append(
            [
                left.trait.name,
                left.get_rating_display(),
                right.trait.name if right else "",
                right.get_rating_display() if right else "",
            ]
        )
    table = Table(rows, colWidths=[4.5 * cm, 4.5 * cm, 4.5 * cm, 4.5 * cm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _psychomotor_legend() -> Paragraph:
    key = " · ".join(f"{value}={label}" for value, label in PSYCHOMOTOR_RATING_LABELS.items())
    return Paragraph(f"<b>Rating key:</b> {key}", _BODY)


def _grading_legend(school) -> Paragraph | None:
    """The active grading scheme's own bands, printed once so the grade
    letters on the subjects table above are self-explanatory on a
    standalone printout — None when the school hasn't configured a
    GradingScheme yet (report_card_service._resolve_grade already
    tolerates that; this mirrors the same best-effort fallback)."""
    scheme = (
        GradingScheme.objects.filter(school=school, is_default=True).first()
        or GradingScheme.objects.filter(school=school).first()
    )
    if scheme is None:
        return None
    bands = GradeBand.objects.filter(grading_scheme=scheme).order_by("-min_score")
    if not bands:
        return None
    key = " · ".join(f"{band.grade} ({band.min_score}-{band.max_score})" for band in bands)
    return Paragraph(f"<b>Grading key ({scheme.name}):</b> {key}", _BODY)


def _verification_url(report_card: ReportCard) -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/report/verify/{report_card.verification_code}"


def _qr_code(data: str, size: float) -> Drawing:
    widget = QrCodeWidget(data)
    x1, y1, x2, y2 = widget.getBounds()
    drawing = Drawing(size, size, transform=[size / (x2 - x1), 0, 0, size / (y2 - y1), 0, 0])
    drawing.add(widget)
    return drawing


def _verification_footer(report_card: ReportCard) -> Table:
    """A QR code next to the codes it encodes — printed so either a scan
    or a manually-typed verification_code reaches the same public lookup
    (apps.report_cards.views.ReportCardVerifyView)."""
    qr = _qr_code(_verification_url(report_card), size=2.4 * cm)
    text = [
        Paragraph(f"<b>Report Card No:</b> {report_card.report_card_number}", _BODY),
        Paragraph(f"<b>Verification Code:</b> {report_card.verification_code}", _BODY),
        Paragraph("Scan the QR code, or enter the code above, to confirm this report card is genuine.", _BODY),
    ]
    table = Table([[qr, text]], colWidths=[3 * cm, None])
    table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
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
    story.extend(_school_header(school, _student_photo(student)))
    story.append(_student_info_table(report_card))
    story.append(Paragraph("ACADEMIC PERFORMANCE", _HEADING))
    story.append(_subjects_table(report_card))
    grading_legend = _grading_legend(school)
    if grading_legend is not None:
        story.append(Spacer(1, 4))
        story.append(grading_legend)

    story.append(Paragraph("OVERALL PERFORMANCE & ATTENDANCE", _HEADING))
    story.append(_overview_table(report_card))

    psychomotor_table = _psychomotor_table(report_card)
    if psychomotor_table is not None:
        story.append(Paragraph("AFFECTIVE & PSYCHOMOTOR DOMAIN", _HEADING))
        story.append(psychomotor_table)
        story.append(Spacer(1, 4))
        story.append(_psychomotor_legend())

    story.append(Paragraph("COMMENTS", _HEADING))
    story.extend(_signature_block("Teacher's comment", report_card.teacher_comment, "Teacher"))
    story.extend(_signature_block("Principal's comment", report_card.principal_comment, "Principal"))

    story.append(Spacer(1, 10))
    next_term = (
        report_card.next_term_begins.strftime("%d %B %Y") if report_card.next_term_begins else "—"
    )
    story.append(Paragraph(f"<b>Next term begins:</b> {next_term}", _BODY))
    story.append(Spacer(1, 8))
    story.append(_verification_footer(report_card))

    doc.build(story)
    return buffer.getvalue()
