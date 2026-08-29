"""§4/§6/§18 ARCHITECTURE.md (Milestone 7). GradingScheme/GradeBand convert
a raw score into a letter grade; Exam/ExamSchedule/Invigilator cover exam
logistics; Assessment is one gradable item (test/quiz/.../exam) on a
ClassSubject, optionally tied to an Exam header when its type is "exam";
Result is one student's score on one Assessment, carrying the
enter->submit->review->verify->publish workflow (§18's named exit
criterion) as a `status` field plus ResultWorkflowState, an append-only
audit trail of every transition — same current-state-plus-immutable-
history pattern apps.attendance already established for Attendance/
AttendanceAudit, including the same Postgres trigger
(apps.tenancy.db.make_append_only) rather than just an application-layer
convention. ReportCard tracks the async PDF-generation job (§18: "PDF
report cards via Celery") for one student's one term. Question/
QuestionOption/StudentAnswer add a question bank on top of Assessment:
objective question types (multiple_choice/true_false) auto-grade from the
QuestionOption marked correct, subjective types (short_answer/essay) are
graded manually, and finalize_assessment_score rolls a student's answers
up into their Result via the existing enter/update result_service
functions rather than duplicating that logic. Every model denormalizes
`organization` directly, same convention as every other app.
"""
from django.conf import settings
from django.db import models

from apps.core.models import BaseModel
from apps.tenancy.managers import TenantManager

ASSESSMENT_TYPE_CHOICES = [
    ("test", "Test"),
    ("quiz", "Quiz"),
    ("assignment", "Assignment"),
    ("project", "Project"),
    ("practical", "Practical"),
    ("exam", "Exam"),
]

RESULT_STATUS_CHOICES = [
    ("entered", "Entered"),
    ("submitted", "Submitted"),
    ("reviewed", "Reviewed"),
    ("verified", "Verified"),
    ("published", "Published"),
]

REPORT_CARD_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("generating", "Generating"),
    ("ready", "Ready"),
    ("failed", "Failed"),
]

QUESTION_TYPE_CHOICES = [
    ("multiple_choice", "Multiple Choice"),
    ("true_false", "True/False"),
    ("short_answer", "Short Answer"),
    ("essay", "Essay"),
]

OBJECTIVE_QUESTION_TYPES = {"multiple_choice", "true_false"}


class GradingScheme(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    school = models.ForeignKey(
        "schools.School", on_delete=models.PROTECT, related_name="grading_schemes"
    )
    name = models.CharField(max_length=100)
    is_default = models.BooleanField(default=False)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "examinations_grading_scheme"
        constraints = [
            models.UniqueConstraint(fields=["school", "name"], name="uq_grading_scheme_school_name")
        ]

    def __str__(self) -> str:
        return self.name


class GradeBand(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    grading_scheme = models.ForeignKey(GradingScheme, on_delete=models.PROTECT, related_name="bands")
    grade = models.CharField(max_length=10)
    min_score = models.DecimalField(max_digits=5, decimal_places=2)
    max_score = models.DecimalField(max_digits=5, decimal_places=2)
    remark = models.CharField(max_length=100, blank=True, default="")

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "examinations_grade_band"
        constraints = [
            models.UniqueConstraint(fields=["grading_scheme", "grade"], name="uq_grade_band_scheme_grade")
        ]
        ordering = ["-min_score"]

    def __str__(self) -> str:
        return f"{self.grading_scheme}: {self.grade}"


class Exam(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="exams")
    academic_year = models.ForeignKey(
        "schools.AcademicYear", on_delete=models.PROTECT, related_name="exams"
    )
    term = models.ForeignKey("schools.Term", on_delete=models.PROTECT, related_name="exams")
    name = models.CharField(max_length=150)
    start_date = models.DateField()
    end_date = models.DateField()

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "examinations_exam"
        constraints = [models.UniqueConstraint(fields=["term", "name"], name="uq_exam_term_name")]
        ordering = ["-start_date"]

    def __str__(self) -> str:
        return self.name


class ExamSchedule(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    exam = models.ForeignKey(Exam, on_delete=models.PROTECT, related_name="schedules")
    class_subject = models.ForeignKey(
        "academics.ClassSubject", on_delete=models.PROTECT, related_name="exam_schedules"
    )
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.ForeignKey(
        "timetable.Room", null=True, blank=True, on_delete=models.PROTECT, related_name="exam_schedules"
    )

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "examinations_exam_schedule"
        constraints = [
            models.UniqueConstraint(fields=["exam", "class_subject"], name="uq_exam_schedule_exam_subject")
        ]
        ordering = ["date", "start_time"]

    def __str__(self) -> str:
        return f"{self.exam} - {self.class_subject}"


class Invigilator(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    exam_schedule = models.ForeignKey(
        ExamSchedule, on_delete=models.PROTECT, related_name="invigilators"
    )
    teacher = models.ForeignKey(
        "staff.Teacher", on_delete=models.PROTECT, related_name="invigilations"
    )

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "examinations_invigilator"
        constraints = [
            models.UniqueConstraint(
                fields=["exam_schedule", "teacher"], name="uq_invigilator_schedule_teacher"
            )
        ]

    def __str__(self) -> str:
        return f"{self.teacher} @ {self.exam_schedule}"


class Assessment(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    class_subject = models.ForeignKey(
        "academics.ClassSubject", on_delete=models.PROTECT, related_name="assessments"
    )
    term = models.ForeignKey("schools.Term", on_delete=models.PROTECT, related_name="assessments")
    exam = models.ForeignKey(
        Exam, null=True, blank=True, on_delete=models.PROTECT, related_name="assessments"
    )
    name = models.CharField(max_length=150)
    assessment_type = models.CharField(max_length=20, choices=ASSESSMENT_TYPE_CHOICES)
    weight = models.DecimalField(max_digits=5, decimal_places=2)
    max_score = models.DecimalField(max_digits=5, decimal_places=2)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "examinations_assessment"
        constraints = [
            models.UniqueConstraint(
                fields=["class_subject", "term", "name"], name="uq_assessment_subject_term_name"
            )
        ]
        ordering = ["term", "class_subject"]

    def __str__(self) -> str:
        return self.name


class Result(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    assessment = models.ForeignKey(Assessment, on_delete=models.PROTECT, related_name="results")
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="results")
    score = models.DecimalField(max_digits=5, decimal_places=2)
    grade = models.CharField(max_length=10, blank=True, default="")
    remark = models.CharField(max_length=100, blank=True, default="")
    status = models.CharField(max_length=20, choices=RESULT_STATUS_CHOICES, default="entered")

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "examinations_result"
        constraints = [
            models.UniqueConstraint(fields=["assessment", "student"], name="uq_result_assessment_student")
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.student} - {self.assessment}: {self.score}"


class ResultWorkflowState(BaseModel):
    """Append-only: see the module docstring. Only ever inserted, never
    updated or soft-deleted — `updated_by`/`deleted_at` (inherited from
    BaseModel for the same public_id/timestamp shape every other model
    uses) are consequently always unset, and the DB trigger rejects any
    attempt to change that.
    """

    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    result = models.ForeignKey(Result, on_delete=models.PROTECT, related_name="workflow_history")
    previous_status = models.CharField(max_length=20, choices=RESULT_STATUS_CHOICES, blank=True, default="")
    new_status = models.CharField(max_length=20, choices=RESULT_STATUS_CHOICES)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "examinations_result_workflow_state"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.result} : {self.previous_status or '(new)'} -> {self.new_status}"


class Question(BaseModel):
    """One gradable question on an Assessment's question bank. multiple_choice/
    true_false are objective (auto-graded from the QuestionOption marked
    is_correct); short_answer/essay are subjective (graded manually via
    student_answer_service.grade_answer). See finalize_assessment_score for
    how a student's answers roll up into their Result.score.
    """

    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    assessment = models.ForeignKey(Assessment, on_delete=models.PROTECT, related_name="questions")
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPE_CHOICES)
    text = models.TextField()
    marks = models.DecimalField(max_digits=5, decimal_places=2)
    sequence = models.PositiveIntegerField()

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "examinations_question"
        constraints = [
            models.UniqueConstraint(
                fields=["assessment", "sequence"], name="uq_question_assessment_sequence"
            )
        ]
        ordering = ["assessment", "sequence"]

    def __str__(self) -> str:
        return f"{self.assessment} Q{self.sequence}"


class QuestionOption(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    question = models.ForeignKey(Question, on_delete=models.PROTECT, related_name="options")
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    sequence = models.PositiveIntegerField()

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "examinations_question_option"
        constraints = [
            models.UniqueConstraint(
                fields=["question", "sequence"], name="uq_question_option_question_sequence"
            )
        ]
        ordering = ["question", "sequence"]

    def __str__(self) -> str:
        return f"{self.question} - option {self.sequence}"


class StudentAnswer(BaseModel):
    """One student's answer to one Question. `selected_option`/`is_correct`/
    `marks_awarded` are set automatically at submission time for objective
    question types; for subjective types they stay null until a teacher
    calls student_answer_service.grade_answer.
    """

    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    question = models.ForeignKey(Question, on_delete=models.PROTECT, related_name="answers")
    student = models.ForeignKey(
        "students.Student", on_delete=models.PROTECT, related_name="exam_answers"
    )
    selected_option = models.ForeignKey(
        QuestionOption, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    text_answer = models.TextField(blank=True, default="")
    is_correct = models.BooleanField(null=True, blank=True)
    marks_awarded = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    submitted_at = models.DateTimeField()

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "examinations_student_answer"
        constraints = [
            models.UniqueConstraint(
                fields=["question", "student"], name="uq_student_answer_question_student"
            )
        ]
        ordering = ["-submitted_at"]

    def __str__(self) -> str:
        return f"{self.student} -> {self.question}"


class ReportCard(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    student = models.ForeignKey(
        "students.Student", on_delete=models.PROTECT, related_name="report_cards"
    )
    academic_year = models.ForeignKey(
        "schools.AcademicYear", on_delete=models.PROTECT, related_name="report_cards"
    )
    term = models.ForeignKey("schools.Term", on_delete=models.PROTECT, related_name="report_cards")
    status = models.CharField(max_length=20, choices=REPORT_CARD_STATUS_CHOICES, default="pending")
    file_url = models.CharField(max_length=500, blank=True, default="")
    generated_at = models.DateTimeField(null=True, blank=True)
    error_message = models.CharField(max_length=255, blank=True, default="")

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "examinations_report_card"
        constraints = [
            models.UniqueConstraint(fields=["student", "term"], name="uq_report_card_student_term")
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.student} - {self.term}"
