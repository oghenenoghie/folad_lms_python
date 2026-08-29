"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from apps.core.storage import get_presigned_download_url
from apps.reports.models import ReportRequest
from apps.reports.tasks.generation import generate_report
from apps.schools.models import School


def request_report(
    *, school: School, report_type: str, format: str, actor, parameters: dict | None = None
) -> ReportRequest:
    report_request = ReportRequest.objects.create(
        organization=school.organization,
        school=school,
        report_type=report_type,
        format=format,
        parameters=parameters or {},
        requested_by=actor,
        created_by=actor,
        updated_by=actor,
    )
    generate_report.delay(report_request.id)
    return report_request


def get_download_url(report_request: ReportRequest) -> str | None:
    if not report_request.storage_key:
        return None
    return get_presigned_download_url(report_request.storage_key)
