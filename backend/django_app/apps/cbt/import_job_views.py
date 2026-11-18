"""Staff cancellation endpoint for CBT source-import jobs."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.permissions import require_permission
from apps.cbt.models import CBTImportJob
from apps.cbt.services.import_job_service import (
    InvalidImportJobTransition,
    transition_import_job,
)
from apps.core.responses import envelope, error_envelope
from rest_framework.generics import get_object_or_404


class CBTImportJobCancelView(APIView):
    """Cancel an import while it is in a cancellable lifecycle state."""

    def get_permissions(self):
        return [IsAuthenticated(), require_permission("cbt_questions.create")()]

    def post(self, request, public_id):
        job = get_object_or_404(CBTImportJob.objects, public_id=public_id)
        try:
            cancelled = transition_import_job(
                job_id=job.pk,
                organization=request.user.organization,
                to_status="cancelled",
                actor=request.user,
            )
        except InvalidImportJobTransition as exc:
            return error_envelope(str(exc), status=409)

        return envelope({
            "public_id": str(cancelled.public_id),
            "status": cancelled.status,
            "completed_at": cancelled.completed_at,
        })
