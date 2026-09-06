"""Enterprise CBT (Computer-Based Testing) module, Phase 1: the question
bank and its rich-content engine.

Core architectural decision (see the CBT implementation spec this app was
built from): a question's CONTENT, its RESPONSE TYPE, and its SCORING are
independent concerns, not one flat `text`/`option_a..d` row. A `Question`
is a shell (subject/topic/difficulty/marks/status) whose displayable
content lives entirely in its ordered `QuestionBlock`s (paragraph, image,
equation, table, graph, audio, video, diagram, ...) — the same block model
a printed exam, a PDF, and the live student CBT renderer all read, so
there is exactly one representation of a question's content, never one
per output format. `QuestionOption` carries the response side for
choice-based question types and, like a block, can itself hold rich
content rather than being assumed to be plain text.

This deliberately parallels-without-replacing apps.examinations.Question/
QuestionOption/StudentAnswer, which stays exactly as it is for the simple
inline-assessment question bank it already serves. This app is for actual
CBT delivery — exam attempts, timers, randomization, security events, none
of which the existing bank has. A CBT exam's finished score is intended to
flow into an apps.examinations.Assessment (score_category="cbt") and
through the existing result_service, once Phase 3/4 build that pipeline —
never a second, competing result engine.

Every model here follows the same convention as every other domain app:
BaseModel's bigint PK + uuid public_id + audit columns, `organization`
denormalized directly (TenantManager/RLS both key on that literal column),
`objects`/`all_tenants` manager pair.
"""
from django.conf import settings
from django.db import models

from apps.core.models import BaseModel
from apps.tenancy.managers import TenantManager

QUESTION_STATUS_CHOICES = [
    ("draft", "Draft"),
    ("submitted", "Submitted"),
    ("review", "Under Review"),
    ("approved", "Approved"),
    ("published", "Published"),
    ("archived", "Archived"),
]

# A question can move forward one step at a time (draft -> submitted ->
# review -> approved -> published) or be sent back to draft at any point
# (a rejection) or archived from published — see question_service.
# "submitted" -> "approved" directly is also allowed: the reviewer-facing
# API (submit/approve/reject) doesn't require a separate "start review"
# call in between, though a reviewer picking up a question via start_review
# first (submitted -> review) is still a valid path to the same approval.
QUESTION_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"submitted"},
    "submitted": {"review", "approved", "draft"},
    "review": {"approved", "draft"},
    "approved": {"published", "draft"},
    "published": {"archived"},
    "archived": set(),
}

QUESTION_TYPE_CHOICES = [
    ("single_choice", "Single Choice"),
    ("multiple_choice", "Multiple Choice"),
    ("true_false", "True / False"),
    ("short_answer", "Short Answer"),
    ("long_answer", "Long Answer"),
    ("numeric", "Numeric"),
    ("matching", "Matching"),
    ("ordering", "Ordering"),
    ("drag_drop", "Drag and Drop"),
    ("hotspot", "Hotspot"),
    ("label_diagram", "Label Diagram"),
    ("image_selection", "Image Selection"),
]

# Question types scored purely from QuestionOption.is_correct (or, for
# matching/ordering/hotspot, from `content`'s configured correct
# mapping/sequence/target) with no human marking step. Everything else
# (short_answer/long_answer/drag_drop/label_diagram) needs a marker.
AUTO_GRADABLE_QUESTION_TYPES = {
    "single_choice", "multiple_choice", "true_false", "numeric", "matching", "ordering", "hotspot",
    "image_selection",
}

DIFFICULTY_CHOICES = [
    ("easy", "Easy"),
    ("medium", "Medium"),
    ("hard", "Hard"),
]

BLOCK_TYPE_CHOICES = [
    ("paragraph", "Paragraph"),
    ("heading", "Heading"),
    ("image", "Image"),
    ("svg", "SVG"),
    ("equation", "Equation"),
    ("chemical_equation", "Chemical Equation"),
    ("table", "Table"),
    ("graph", "Graph"),
    ("audio", "Audio"),
    ("video", "Video"),
    ("document", "Document"),
    ("diagram", "Diagram"),
    ("callout", "Callout"),
    ("divider", "Divider"),
]

MEDIA_TYPE_CHOICES = [
    ("image", "Image"),
    ("audio", "Audio"),
    ("video", "Video"),
    ("document", "Document"),
    ("svg", "SVG"),
]


class Topic(BaseModel):
    """A curriculum topic within a Subject (e.g. "Algebra" under
    Mathematics) — nothing in apps.academics models this yet, and a
    question bank needs it for topic-weighted exam generation (Phase 3)
    and topic-level analytics (later), so it lives here rather than
    growing apps.academics for a concern only CBT currently has.
    """

    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    subject = models.ForeignKey("academics.Subject", on_delete=models.PROTECT, related_name="cbt_topics")
    name = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "cbt_topic"
        constraints = [models.UniqueConstraint(fields=["subject", "name"], name="uq_cbt_topic_subject_name")]
        ordering = ["subject", "name"]

    def __str__(self) -> str:
        return f"{self.subject} - {self.name}"


class Question(BaseModel):
    """A CBT question bank entry. Carries no displayable content itself —
    see `blocks` (QuestionBlock, ordered) for that — only the metadata a
    question bank/review/exam-builder screen filters and sorts by.
    """

    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    subject = models.ForeignKey("academics.Subject", on_delete=models.PROTECT, related_name="cbt_questions")
    class_level = models.ForeignKey(
        "academics.ClassLevel", on_delete=models.PROTECT, related_name="cbt_questions"
    )
    topic = models.ForeignKey(
        Topic, null=True, blank=True, on_delete=models.SET_NULL, related_name="questions"
    )
    # Auto-generated on first save (e.g. "Q-000124") — see save() below.
    code = models.CharField(max_length=50, blank=True)
    question_type = models.CharField(max_length=30, choices=QUESTION_TYPE_CHOICES)
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default="medium")
    marks = models.DecimalField(max_digits=6, decimal_places=2)
    negative_marks = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=QUESTION_STATUS_CHOICES, default="draft")
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_cbt_questions",
    )

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "cbt_question"
        constraints = [models.UniqueConstraint(fields=["organization", "code"], name="uq_cbt_question_org_code")]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.code or f"Question #{self.pk}"

    def save(self, *args, **kwargs):
        if not self.code:
            from apps.core.codegen import next_sequence_code

            self.code = next_sequence_code(
                queryset=Question.all_tenants.filter(organization_id=self.organization_id),
                field_name="code",
                prefix="Q-",
                width=6,
            )
        super().save(*args, **kwargs)


class QuestionBlock(BaseModel):
    """One ordered piece of a question's displayable content. `content`'s
    shape depends on `block_type` — e.g. `{"html": "..."}` for paragraph/
    heading, `{"media_id": "...", "width": 80, "alignment": "center"}` for
    image, `{"latex": "..."}` for equation, `{"type": "line", "xAxis":
    {...}, "series": [...]}` for graph — validated by
    question_service.validate_block_content per block_type, not by the
    database.
    """

    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="blocks")
    block_type = models.CharField(max_length=30, choices=BLOCK_TYPE_CHOICES)
    content = models.JSONField(default=dict)
    order = models.PositiveIntegerField()

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "cbt_question_block"
        constraints = [
            models.UniqueConstraint(fields=["question", "order"], name="uq_cbt_question_block_question_order")
        ]
        ordering = ["question", "order"]
        indexes = [models.Index(fields=["question", "order"])]

    def __str__(self) -> str:
        return f"{self.question} block #{self.order} ({self.block_type})"


class QuestionOption(BaseModel):
    """One answer choice for a choice-based question_type. Like a block,
    `content` may hold rich content (text, an image reference, an
    equation) rather than being assumed plain text — see the module
    docstring. `is_correct` covers single/multiple_choice/true_false
    directly; for matching/ordering/hotspot/image_selection the correct
    mapping lives in `content` instead (this flag is unused there).
    """

    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="options")
    label = models.CharField(max_length=10)
    content = models.JSONField(default=dict)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField()
    explanation = models.JSONField(default=dict, blank=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "cbt_question_option"
        constraints = [
            models.UniqueConstraint(fields=["question", "order"], name="uq_cbt_question_option_question_order")
        ]
        ordering = ["question", "order"]

    def __str__(self) -> str:
        return f"{self.question} - {self.label}"


class QuestionVersion(BaseModel):
    """An immutable snapshot of a Question's full content (its own fields
    plus every block/option) taken whenever a *published* question is
    edited. A CBT exam snapshots the Question it uses at publish time
    (Phase 3), but that snapshot is only ever as good as knowing which
    version was current then — this is what lets an old, already-delivered
    exam stay reproducible even after the live question bank moves on,
    and lets a reviewer see exactly what changed between versions.
    """

    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="versions")
    version_number = models.PositiveIntegerField()
    content = models.JSONField()

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "cbt_question_version"
        constraints = [
            models.UniqueConstraint(
                fields=["question", "version_number"], name="uq_cbt_question_version_question_number"
            )
        ]
        ordering = ["-version_number"]

    def __str__(self) -> str:
        return f"{self.question} v{self.version_number}"


class CBTMedia(BaseModel):
    """One uploaded media asset (image/audio/video/document/svg) available
    for reuse across question blocks and options. Follows apps.documents'
    "store-once-access-later" shape (a `storage_key`, not a persisted URL —
    see apps.core.storage's module docstring) rather than the spec's own
    sketch of a raw Cloudinary `url` field: this project's actual storage
    abstraction is S3/R2/MinIO-agnostic, not Cloudinary-specific, so a
    fresh presigned URL is computed per request instead.
    """

    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    name = models.CharField(max_length=255)
    media_type = models.CharField(max_length=20, choices=MEDIA_TYPE_CHOICES)
    storage_key = models.CharField(max_length=500)
    content_type = models.CharField(max_length=100)
    size_bytes = models.PositiveIntegerField()
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    alt_text = models.TextField(blank=True, default="")
    caption = models.TextField(blank=True, default="")

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "cbt_media"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name


# ---------------------------------------------------------------------------
# Phase 3: exams — assembling published/approved bank questions into a
# deliverable examination. A CBTExam intentionally does NOT create or
# reference an apps.examinations.Assessment here: that linkage (so a
# finished attempt's score flows into the existing Result/report-card
# pipeline) only makes sense once a specific student's specific enrollment
# resolves to a specific ClassSubject, which is Phase 4's (ExamAttempt)
# concern, not exam authoring's.
# ---------------------------------------------------------------------------

EXAM_TYPE_CHOICES = [
    ("ca", "Continuous Assessment"),
    ("test", "Test"),
    ("quiz", "Quiz"),
    ("midterm", "Mid-Term"),
    ("terminal", "Terminal"),
    ("mock", "Mock"),
    ("entrance", "Entrance"),
    ("promotion", "Promotion"),
]

# scheduled/open/closed/marking describe the exam's *delivery* lifecycle —
# derived from start_at/end_at and attempt activity once Phase 4
# (ExamAttempt) exists to drive them. Phase 3's exam_service only ever
# moves an exam between draft, published and archived; the other four are
# declared now so the column doesn't need a migration when Phase 4 starts
# setting them.
EXAM_STATUS_CHOICES = [
    ("draft", "Draft"),
    ("scheduled", "Scheduled"),
    ("open", "Open"),
    ("closed", "Closed"),
    ("marking", "Marking"),
    ("published", "Published"),
    ("archived", "Archived"),
]

EXAM_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"published"},
    "published": {"archived"},
    "archived": set(),
}

# An exam may only draw on questions a reviewer has already vetted — see
# exam_service.add_question_to_exam.
EXAM_ELIGIBLE_QUESTION_STATUSES = {"approved", "published"}


class CBTExam(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="cbt_exams")
    academic_year = models.ForeignKey(
        "schools.AcademicYear", on_delete=models.PROTECT, related_name="cbt_exams"
    )
    term = models.ForeignKey("schools.Term", on_delete=models.PROTECT, related_name="cbt_exams")
    subject = models.ForeignKey("academics.Subject", on_delete=models.PROTECT, related_name="cbt_exams")
    class_level = models.ForeignKey(
        "academics.ClassLevel", on_delete=models.PROTECT, related_name="cbt_exams"
    )
    name = models.CharField(max_length=255)
    # Auto-generated on first save (e.g. "CBT-000012") — see save() below.
    code = models.CharField(max_length=50, blank=True)
    exam_type = models.CharField(max_length=30, choices=EXAM_TYPE_CHOICES)
    duration_minutes = models.PositiveIntegerField()
    # Derived at publish time from the sum of every ExamQuestion's
    # effective marks (marks_override or the question's own bank marks) —
    # never hand-entered, so it can never drift from what the exam
    # actually contains. 0 until then.
    total_marks = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    pass_mark = models.DecimalField(max_digits=8, decimal_places=2)
    instructions = models.JSONField(default=dict, blank=True)
    randomize_questions = models.BooleanField(default=True)
    randomize_options = models.BooleanField(default=True)
    allow_resume = models.BooleanField(default=True)
    negative_marking = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=EXAM_STATUS_CHOICES, default="draft")
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    published_at = models.DateTimeField(null=True, blank=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "cbt_exam"
        constraints = [models.UniqueConstraint(fields=["organization", "code"], name="uq_cbt_exam_org_code")]
        ordering = ["-start_at"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.code:
            from apps.core.codegen import next_sequence_code

            self.code = next_sequence_code(
                queryset=CBTExam.all_tenants.filter(organization_id=self.organization_id),
                field_name="code",
                prefix="CBT-",
                width=6,
            )
        super().save(*args, **kwargs)


class ExamSection(BaseModel):
    """An optional named grouping of an exam's questions (e.g. "Section A —
    Objective"). An exam with no sections is a single flat question list —
    ExamQuestion.section is nullable for exactly that case.
    """

    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    exam = models.ForeignKey(CBTExam, on_delete=models.CASCADE, related_name="sections")
    name = models.CharField(max_length=150)
    instructions = models.JSONField(default=dict, blank=True)
    order = models.PositiveIntegerField()
    # The section's advertised/target marks (e.g. "20 marks" on a printed
    # instruction sheet) — independent of, and not cross-validated against,
    # the sum of its questions' actual marks.
    marks = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "cbt_exam_section"
        constraints = [
            models.UniqueConstraint(fields=["exam", "order"], name="uq_cbt_exam_section_exam_order")
        ]
        ordering = ["exam", "order"]

    def __str__(self) -> str:
        return f"{self.exam} - {self.name}"


class ExamQuestion(BaseModel):
    """The join between an exam and a bank Question, plus (once published)
    an immutable snapshot of that question's full content — see the module
    docstring on QuestionVersion for why: the live question bank can keep
    evolving after this exam ships without ever changing what this exam
    actually delivered.
    """

    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    exam = models.ForeignKey(CBTExam, on_delete=models.CASCADE, related_name="exam_questions")
    section = models.ForeignKey(
        ExamSection, null=True, blank=True, on_delete=models.SET_NULL, related_name="exam_questions"
    )
    question = models.ForeignKey(Question, on_delete=models.PROTECT, related_name="exam_questions")
    order = models.PositiveIntegerField()
    marks_override = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    # Empty until the exam is published — see exam_service.publish_exam.
    snapshot = models.JSONField(default=dict, blank=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "cbt_exam_question"
        constraints = [
            models.UniqueConstraint(fields=["exam", "question"], name="uq_cbt_exam_question_exam_question"),
            models.UniqueConstraint(fields=["exam", "order"], name="uq_cbt_exam_question_exam_order"),
        ]
        ordering = ["exam", "order"]

    def __str__(self) -> str:
        return f"{self.exam} - {self.question}"

    @property
    def marks(self):
        """`marks_override` always wins. Otherwise, once published, the
        frozen `snapshot`'s marks — never the live question's, which may
        have been edited (even re-marked) since this exam locked it in —
        matches exactly what a candidate was actually told this question
        was worth. Only a still-draft exam (no snapshot yet) falls back to
        the live question.
        """
        from decimal import Decimal

        if self.marks_override is not None:
            return self.marks_override
        if self.snapshot:
            return Decimal(self.snapshot["marks"])
        return self.question.marks


class ExamCandidate(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    exam = models.ForeignKey(CBTExam, on_delete=models.CASCADE, related_name="candidates")
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="cbt_candidacies")
    candidate_number = models.CharField(max_length=50, blank=True)
    extra_time_minutes = models.PositiveIntegerField(default=0)
    is_eligible = models.BooleanField(default=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "cbt_exam_candidate"
        constraints = [
            models.UniqueConstraint(fields=["exam", "student"], name="uq_cbt_exam_candidate_exam_student")
        ]
        ordering = ["exam", "candidate_number"]

    def __str__(self) -> str:
        return f"{self.exam} - {self.student}"

    def save(self, *args, **kwargs):
        if not self.candidate_number:
            from apps.core.codegen import next_sequence_code

            self.candidate_number = next_sequence_code(
                queryset=ExamCandidate.all_tenants.filter(exam_id=self.exam_id),
                field_name="candidate_number",
                prefix=f"{self.exam.code}-",
                width=4,
            )
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# Phase 4: exam delivery — one candidate's attempt, their answers, and the
# server-authoritative timer. `question_order` is the ONE place
# randomization ever happens: computed once at start_attempt and stored,
# never recomputed per request (§16/§17 of the spec: "never randomize on
# every API request", "the same attempt can be reconstructed after
# refresh/reconnect").
# ---------------------------------------------------------------------------

ATTEMPT_STATUS_CHOICES = [
    ("not_started", "Not Started"),
    ("in_progress", "In Progress"),
    ("submitted", "Submitted"),
    ("expired", "Expired"),
    ("abandoned", "Abandoned"),
]

ATTEMPT_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "not_started": {"in_progress"},
    "in_progress": {"submitted", "expired", "abandoned"},
    "submitted": set(),
    "expired": set(),
    "abandoned": set(),
}


class ExamAttempt(BaseModel):
    """One candidate's single attempt at an exam — a OneToOne on
    ExamCandidate rather than allowing several rows per candidate, since
    "resume" (CBTExam.allow_resume) means reconnecting to *this same*
    attempt and its already-stored question_order, never starting a fresh
    one.
    """

    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    exam = models.ForeignKey(CBTExam, on_delete=models.PROTECT, related_name="attempts")
    candidate = models.OneToOneField(ExamCandidate, on_delete=models.PROTECT, related_name="attempt")
    # The exam_question public_ids, in the order this candidate sees them —
    # randomized once at start if exam.randomize_questions, else natural
    # ExamQuestion.order. See the module note above on why this is stored,
    # not recomputed.
    question_order = models.JSONField(default=list, blank=True)
    # {exam_question public_id: [option label, ...]} — the per-question
    # option display order, randomized once at start if
    # exam.randomize_options, for every question type whose options are
    # genuine on-screen choices (not the numeric/matching/ordering/hotspot
    # types, whose "options" are an answer key with nothing to shuffle).
    # Same never-recompute-per-request rule as question_order.
    option_orders = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=ATTEMPT_STATUS_CHOICES, default="not_started")
    started_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    # started_at + exam.duration_minutes + candidate.extra_time_minutes,
    # fixed at start_attempt — the single source of truth a heartbeat call
    # compares the current time against; never recomputed from the client.
    expires_at = models.DateTimeField(null=True, blank=True)
    score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    percentage = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    grade = models.CharField(max_length=10, blank=True, default="")
    passed = models.BooleanField(default=False)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    # Set once, automatically, by attempt_service.log_attempt_event once
    # this attempt's count of SUSPICIOUS_EVENT_TYPES crosses
    # AUTO_FLAG_THRESHOLD — a monotonic signal for a human reviewer to
    # look at, never cleared automatically (and not yet clearable at all;
    # that's a staff-review workflow for a later phase).
    flagged_for_review = models.BooleanField(default=False)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "cbt_exam_attempt"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.candidate} - {self.exam}"


class StudentAnswer(BaseModel):
    """One answer to one ExamQuestion within a single attempt. `response`'s
    shape depends on the question's type (see the spec): e.g.
    `{"selected_option_id": "..."}` for single_choice, `{"value": 42.5}`
    for numeric, `{"matches": {"A": "3", ...}}` for matching, `{"x":
    432, "y": 271}` for hotspot. `graded_at` is set the moment a mark is
    final — immediately at submit for an auto-gradable type, or whenever a
    marker grades a subjective one — so attempt_service can tell "every
    answer has been graded" from "there are still ungraded ones" without
    guessing from `marks_awarded` alone (a legitimate 0 looks identical to
    "not graded yet" otherwise).
    """

    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    attempt = models.ForeignKey(ExamAttempt, on_delete=models.CASCADE, related_name="answers")
    exam_question = models.ForeignKey(ExamQuestion, on_delete=models.PROTECT, related_name="cbt_student_answers")
    response = models.JSONField(default=dict, blank=True)
    is_correct = models.BooleanField(null=True, blank=True)
    marks_awarded = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    graded_at = models.DateTimeField(null=True, blank=True)
    time_spent_seconds = models.PositiveIntegerField(default=0)
    flagged = models.BooleanField(default=False)
    answered_at = models.DateTimeField(auto_now=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "cbt_student_answer"
        constraints = [
            models.UniqueConstraint(fields=["attempt", "exam_question"], name="uq_cbt_student_answer_attempt_question")
        ]
        ordering = ["attempt", "exam_question"]

    def __str__(self) -> str:
        return f"{self.attempt} - {self.exam_question}"


EVENT_TYPE_CHOICES = [
    ("tab_hidden", "Tab Hidden"),
    ("tab_visible", "Tab Visible"),
    ("fullscreen_exit", "Fullscreen Exit"),
    ("fullscreen_enter", "Fullscreen Enter"),
    ("window_blur", "Window Blur"),
    ("window_focus", "Window Focus"),
    ("copy_attempt", "Copy Attempted"),
    ("paste_attempt", "Paste Attempted"),
    ("right_click", "Right-Click Attempted"),
    ("disconnect", "Connection Lost"),
    ("reconnect", "Reconnected"),
]


class ExamAttemptEvent(BaseModel):
    """An append-only proctoring signal reported by the candidate's client
    during a live attempt (visibility/fullscreen/focus changes, copy/paste,
    right-click, connectivity) — see attempt_service.log_attempt_event for
    which of these count toward auto-flagging ExamAttempt.flagged_for_review.
    Never mutated or deleted once written; a full record of what happened
    during the attempt, for a human reviewer to look at later.
    """

    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    attempt = models.ForeignKey(ExamAttempt, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES)
    metadata = models.JSONField(default=dict, blank=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "cbt_exam_attempt_event"
        ordering = ["attempt", "created_at"]

    def __str__(self) -> str:
        return f"{self.attempt} - {self.event_type}"
