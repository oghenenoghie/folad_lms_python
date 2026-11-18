"""Explicit staff action for committing a validated CBT import."""
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.permissions import require_permission
from apps.core.responses import envelope, error_envelope
from apps.cbt.models import CBTImportJob
from apps.cbt.services.import_commit_service import ImportCommitError, commit_import_job


class CBTImportJobCommitView(APIView):
    """Create draft questions from a fully validated import ledger."""

    def get_permissions(self):
        return [IsAuthenticated(), require_permission("cbt_questions.create")()]

    def post(self, request, public_id):
        from rest_framework.generics import get_object_or_404

        job = get_object_or_404(CBTImportJob.objects, public_id=public_id)
        try:
            summary = commit_import_job(
                job_id=job.pk,
                organization=job.organization,
                actor=request.user,
            )
        except ImportCommitError as exc:
            return error_envelope(str(exc), status=409)
        return envelope({
            "public_id": str(job.public_id),
            "status": "completed",
            "summary": summary,
        })
