"""§6/§18 ARCHITECTURE.md (Milestone 9). LibraryBook is a catalogue title;
LibraryCopy is one physical, loanable unit of a book (a school may hold
several copies of the same title) — Loans reference a Copy, never a Book
directly, so "is this exact copy out" is a plain status check. LibraryMember
wraps either a Student or a Staff member (never both — see the check
constraint) so Loan/Fine don't need to branch on borrower type. Every model
denormalizes `organization` directly, same convention as every other app.
"""
from django.db import models

from apps.core.models import BaseModel
from apps.tenancy.managers import TenantManager

COPY_STATUS_CHOICES = [
    ("available", "Available"),
    ("loaned", "Loaned"),
    ("lost", "Lost"),
    ("damaged", "Damaged"),
]

MEMBER_TYPE_CHOICES = [
    ("student", "Student"),
    ("staff", "Staff"),
]

LOAN_STATUS_CHOICES = [
    ("borrowed", "Borrowed"),
    ("returned", "Returned"),
    ("overdue", "Overdue"),
    ("lost", "Lost"),
]

FINE_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("paid", "Paid"),
    ("waived", "Waived"),
]


class LibraryBook(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="library_books")
    isbn = models.CharField(max_length=20, blank=True, default="")
    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255, blank=True, default="")
    publisher = models.CharField(max_length=255, blank=True, default="")
    category = models.CharField(max_length=100, blank=True, default="")
    published_year = models.PositiveIntegerField(null=True, blank=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "library_book"
        ordering = ["title"]

    def __str__(self) -> str:
        return self.title


class LibraryCopy(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    book = models.ForeignKey(LibraryBook, on_delete=models.PROTECT, related_name="copies")
    # Optional: left blank, save() assigns the next copy number for this
    # book (e.g. "1", "2", "3") — see apps.core.codegen.
    copy_number = models.CharField(max_length=30, blank=True)
    status = models.CharField(max_length=20, choices=COPY_STATUS_CHOICES, default="available")

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "library_copy"
        constraints = [
            models.UniqueConstraint(fields=["book", "copy_number"], name="uq_library_copy_book_number")
        ]
        ordering = ["copy_number"]

    def __str__(self) -> str:
        return f"{self.book} #{self.copy_number}"

    def save(self, *args, **kwargs):
        if not self.copy_number:
            from apps.core.codegen import next_sequence_code

            self.copy_number = next_sequence_code(
                queryset=LibraryCopy.all_tenants.filter(book_id=self.book_id),
                field_name="copy_number",
                width=1,
            )
        super().save(*args, **kwargs)


class LibraryMember(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="library_members")
    member_type = models.CharField(max_length=10, choices=MEMBER_TYPE_CHOICES)
    student = models.ForeignKey(
        "students.Student", null=True, blank=True, on_delete=models.PROTECT, related_name="library_memberships"
    )
    staff = models.ForeignKey(
        "staff.Staff", null=True, blank=True, on_delete=models.PROTECT, related_name="library_memberships"
    )
    # Optional: left blank, save() assigns the next sequential number for
    # this school (e.g. "LIB-0001") — see apps.core.codegen.
    membership_number = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "library_member"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "membership_number"], name="uq_library_member_school_number"
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(member_type="student", student__isnull=False, staff__isnull=True)
                    | models.Q(member_type="staff", staff__isnull=False, student__isnull=True)
                ),
                name="ck_library_member_type_matches_link",
            ),
        ]

    def __str__(self) -> str:
        return self.membership_number

    def save(self, *args, **kwargs):
        if not self.membership_number:
            from apps.core.codegen import next_sequence_code

            self.membership_number = next_sequence_code(
                queryset=LibraryMember.all_tenants.filter(school_id=self.school_id),
                field_name="membership_number",
                prefix="LIB-",
            )
        super().save(*args, **kwargs)


class LibraryLoan(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    copy = models.ForeignKey(LibraryCopy, on_delete=models.PROTECT, related_name="loans")
    member = models.ForeignKey(LibraryMember, on_delete=models.PROTECT, related_name="loans")
    borrowed_date = models.DateField()
    due_date = models.DateField()
    returned_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=LOAN_STATUS_CHOICES, default="borrowed")

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "library_loan"
        constraints = [
            # A copy can only be out on one open loan at a time — enforced as
            # a real (Postgres-only) partial unique index, not just an
            # application-layer check, same philosophy as apps.timetable's
            # double-booking constraints.
            models.UniqueConstraint(
                fields=["copy"],
                condition=models.Q(status__in=["borrowed", "overdue"]),
                name="uq_library_loan_one_open_per_copy",
            )
        ]
        ordering = ["-borrowed_date"]

    def __str__(self) -> str:
        return f"{self.member} - {self.copy}"


class LibraryFine(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    loan = models.ForeignKey(LibraryLoan, on_delete=models.PROTECT, related_name="fines")
    amount_minor = models.BigIntegerField()
    currency_code = models.CharField(max_length=3)
    reason = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(max_length=20, choices=FINE_STATUS_CHOICES, default="pending")
    paid_at = models.DateTimeField(null=True, blank=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "library_fine"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Fine on {self.loan}: {self.amount_minor}"
