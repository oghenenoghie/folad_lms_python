"""Thin views, fat services (§11 ARCHITECTURE.md). AssignmentSubmission has
two create paths — plain JSON for a text submission (this module's
`AssignmentSubmissionListCreateView.create`) and multipart for a file one
(`AssignmentSubmissionUploadView`) — since DRF's ModelSerializer can't
cleanly express "exactly one of these two shapes" as a single JSON schema.
Grading and downloading are dedicated endpoints, not a generic PATCH.
"""
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.permissions import require_permission
from apps.core.generics import TenantListCreateAPIView, TenantRetrieveAPIView, TenantRetrieveUpdateDestroyAPIView
from apps.core.responses import envelope, error_envelope
from apps.core.storage import InvalidUpload
from apps.students.models import Student

from .models import Assignment, AssignmentSubmission
from .serializers import AssignmentSerializer, AssignmentSubmissionSerializer
from .services import assignment_service, submission_service
from .services.exceptions import AssignmentError


class AssignmentListCreateView(TenantListCreateAPIView):
    serializer_class = AssignmentSerializer

    def get_queryset(self):
        qs = Assignment.objects.filter(deleted_at__isnull=True)
        class_subject_id = self.request.query_params.get("class_subject_id")
        term_id = self.request.query_params.get("term_id")
        if class_subject_id:
            qs = qs.filter(class_subject__public_id=class_subject_id)
        if term_id:
            qs = qs.filter(term__public_id=term_id)
        return qs

    def get_permissions(self):
        code = "assignments.create" if self.request.method == "POST" else "assignments.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        class_subject = data.pop("class_subject")
        term = data.pop("term")
        serializer.instance = assignment_service.create_assignment(
            class_subject=class_subject, term=term, actor=self.request.user, **data
        )


class AssignmentDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = AssignmentSerializer

    def get_queryset(self):
        return Assignment.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {"GET": "assignments.view", "PATCH": "assignments.update", "DELETE": "assignments.delete"}[
            self.request.method
        ]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("class_subject", None)
        data.pop("term", None)
        assignment_service.update_assignment(assignment=serializer.instance, actor=self.request.user, **data)

    def perform_destroy(self, instance):
        assignment_service.delete_assignment(assignment=instance, actor=self.request.user)


class AssignmentSubmissionListCreateView(TenantListCreateAPIView):
    serializer_class = AssignmentSubmissionSerializer

    def get_queryset(self):
        qs = AssignmentSubmission.objects.filter(deleted_at__isnull=True)
        assignment_id = self.request.query_params.get("assignment_id")
        student_id = self.request.query_params.get("student_id")
        if assignment_id:
            qs = qs.filter(assignment__public_id=assignment_id)
        if student_id:
            qs = qs.filter(student__public_id=student_id)
        return qs

    def get_permissions(self):
        code = (
            "assignment_submissions.create"
            if self.request.method == "POST"
            else "assignment_submissions.view"
        )
        return [IsAuthenticated(), require_permission(code)()]

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except AssignmentError as exc:
            return error_envelope(str(exc), status=400)

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        assignment = data.pop("assignment")
        student = data.pop("student")
        serializer.instance = submission_service.submit_text(
            assignment=assignment, student=student, actor=self.request.user,
            text_content=data.get("text_content", ""),
        )


class AssignmentSubmissionDetailView(TenantRetrieveAPIView):
    serializer_class = AssignmentSubmissionSerializer

    def get_queryset(self):
        return AssignmentSubmission.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        return [IsAuthenticated(), require_permission("assignment_submissions.view")()]


class AssignmentSubmissionUploadView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated, require_permission("assignment_submissions.create")]

    def post(self, request):
        try:
            assignment = Assignment.objects.filter(deleted_at__isnull=True).get(
                public_id=request.data.get("assignment")
            )
            student = Student.objects.get(public_id=request.data.get("student"))
        except (Assignment.DoesNotExist, Student.DoesNotExist, ValueError, TypeError):
            return error_envelope("assignment or student not found", status=404)

        file_obj = request.FILES.get("file")
        if file_obj is None:
            return error_envelope("a file is required", status=400)

        try:
            submission = submission_service.submit_file(
                assignment=assignment, student=student, actor=request.user,
                file_name=file_obj.name, content=file_obj.read(), content_type=file_obj.content_type,
            )
        except (AssignmentError, InvalidUpload) as exc:
            return error_envelope(str(exc), status=400)
        return envelope(
            AssignmentSubmissionSerializer(submission).data, message="submission uploaded", status=201
        )


class AssignmentSubmissionDownloadView(APIView):
    permission_classes = [IsAuthenticated, require_permission("assignment_submissions.view")]

    def get(self, request, public_id):
        try:
            submission = AssignmentSubmission.objects.filter(deleted_at__isnull=True).get(public_id=public_id)
        except AssignmentSubmission.DoesNotExist:
            return error_envelope("submission not found", status=404)
        url = submission_service.get_download_url(submission)
        if url is None:
            return error_envelope("this submission has no file", status=404)
        return envelope({"url": url})


class AssignmentSubmissionGradeView(APIView):
    permission_classes = [IsAuthenticated, require_permission("assignment_submissions.update")]

    def post(self, request, public_id):
        try:
            submission = AssignmentSubmission.objects.filter(deleted_at__isnull=True).get(public_id=public_id)
        except AssignmentSubmission.DoesNotExist:
            return error_envelope("submission not found", status=404)
        score = request.data.get("score")
        if score is None:
            return error_envelope("score is required", status=400)
        submission = submission_service.grade_submission(
            submission=submission, actor=request.user, score=score,
            feedback=request.data.get("feedback", ""),
        )
        return envelope(AssignmentSubmissionSerializer(submission).data, message="submission graded")
