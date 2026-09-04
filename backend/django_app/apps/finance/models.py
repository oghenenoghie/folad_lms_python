"""§5/§6/§18 ARCHITECTURE.md (Milestone 8). FeeStructure/FeeItem define what a
term charges; Discount/Scholarship define reductions; Invoice/InvoiceLine bill
a student, InvoiceLine snapshotting each FeeItem's amount at billing time (a
later FeeItem price change must never retroactively alter an issued invoice);
Payment records money received against an Invoice and Refund reverses part or
all of one Payment — never edited or deleted in place, only reversed, per
§18's "refunds as reversals" exit criterion. LedgerEntry is the append-only
double-entry trail every Invoice/Payment/Refund posts to (same DB-trigger
append-only pattern as apps.examinations.ResultWorkflowState), so ref_type/
ref_id are plain fields (not a real FK) — deliberately decoupled from the
source row's lifecycle, matching §6's ERD. All monetary amounts are integer
minor units (see backend/shared/money.py) with a denormalized `currency_code`
(from Organization.currency_code) — never a float. Every model denormalizes
`organization` directly, same convention as every other app.
"""
from django.db import models

from apps.core.models import BaseModel
from apps.tenancy.managers import TenantManager

INVOICE_STATUS_CHOICES = [
    ("draft", "Draft"),
    ("issued", "Issued"),
    ("partially_paid", "Partially paid"),
    ("paid", "Paid"),
    ("cancelled", "Cancelled"),
]

PAYMENT_METHOD_CHOICES = [
    ("cash", "Cash"),
    ("bank_transfer", "Bank transfer"),
    ("card", "Card"),
    ("ussd", "USSD"),
    ("cheque", "Cheque"),
]

PAYMENT_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("successful", "Successful"),
    ("failed", "Failed"),
]

REFUND_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("completed", "Completed"),
    ("failed", "Failed"),
]

RECEIPT_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("generating", "Generating"),
    ("ready", "Ready"),
    ("failed", "Failed"),
]

DISCOUNT_TYPE_CHOICES = [
    ("percentage", "Percentage"),
    ("fixed_amount", "Fixed amount"),
]


class FeeStructure(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="fee_structures")
    academic_year = models.ForeignKey(
        "schools.AcademicYear", on_delete=models.PROTECT, related_name="fee_structures"
    )
    term = models.ForeignKey("schools.Term", on_delete=models.PROTECT, related_name="fee_structures")
    name = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "finance_fee_structure"
        constraints = [
            models.UniqueConstraint(fields=["term", "name"], name="uq_fee_structure_term_name")
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name


class FeeItem(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    fee_structure = models.ForeignKey(FeeStructure, on_delete=models.PROTECT, related_name="items")
    name = models.CharField(max_length=150)
    amount_minor = models.BigIntegerField()
    currency_code = models.CharField(max_length=3)
    is_mandatory = models.BooleanField(default=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "finance_fee_item"
        constraints = [
            models.UniqueConstraint(fields=["fee_structure", "name"], name="uq_fee_item_structure_name")
        ]
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.fee_structure}: {self.name}"


class Discount(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="discounts")
    name = models.CharField(max_length=150)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    fixed_amount_minor = models.BigIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "finance_discount"
        constraints = [
            models.UniqueConstraint(fields=["school", "name"], name="uq_discount_school_name"),
            models.CheckConstraint(
                condition=(
                    models.Q(discount_type="percentage", percentage__isnull=False, fixed_amount_minor__isnull=True)
                    | models.Q(discount_type="fixed_amount", fixed_amount_minor__isnull=False, percentage__isnull=True)
                ),
                name="ck_discount_value_matches_type",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class Scholarship(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="scholarships")
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="scholarships")
    discount = models.ForeignKey(Discount, on_delete=models.PROTECT, related_name="scholarships")
    academic_year = models.ForeignKey(
        "schools.AcademicYear", on_delete=models.PROTECT, related_name="scholarships"
    )
    is_active = models.BooleanField(default=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "finance_scholarship"
        constraints = [
            models.UniqueConstraint(
                fields=["student", "discount", "academic_year"], name="uq_scholarship_student_discount_year"
            )
        ]

    def __str__(self) -> str:
        return f"{self.student} - {self.discount}"


class Invoice(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="invoices")
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="invoices")
    academic_year = models.ForeignKey(
        "schools.AcademicYear", on_delete=models.PROTECT, related_name="invoices"
    )
    term = models.ForeignKey("schools.Term", on_delete=models.PROTECT, related_name="invoices")
    # Optional: left blank, save() assigns the next sequential number for
    # this school (e.g. "INV-0001") — see apps.core.codegen.
    invoice_number = models.CharField(max_length=40, blank=True)
    total_minor = models.BigIntegerField(default=0)
    currency_code = models.CharField(max_length=3)
    status = models.CharField(max_length=20, choices=INVOICE_STATUS_CHOICES, default="draft")
    due_date = models.DateField(null=True, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    # Set by apps.finance.services.reminder_service whenever a fee reminder
    # notification is sent for this invoice — the cooldown that keeps the
    # daily send_fee_reminders task from re-notifying the same invoice
    # every single day it stays due-soon/overdue.
    reminder_sent_at = models.DateTimeField(null=True, blank=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "finance_invoice"
        constraints = [
            models.UniqueConstraint(fields=["school", "invoice_number"], name="uq_invoice_school_number")
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.invoice_number

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            from apps.core.codegen import next_sequence_code

            self.invoice_number = next_sequence_code(
                queryset=Invoice.all_tenants.filter(school_id=self.school_id),
                field_name="invoice_number",
                prefix="INV-",
            )
        super().save(*args, **kwargs)


class InvoiceLine(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="lines")
    # Nullable: a line may be a one-off charge with no backing FeeItem. PROTECT
    # (not CASCADE/SET_NULL) since a FeeItem must never disappear out from
    # under a line that already snapshotted its price onto an issued invoice.
    fee_item = models.ForeignKey(
        FeeItem, null=True, blank=True, on_delete=models.PROTECT, related_name="invoice_lines"
    )
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    unit_amount_minor = models.BigIntegerField()
    discount = models.ForeignKey(
        Discount, null=True, blank=True, on_delete=models.PROTECT, related_name="invoice_lines"
    )
    discount_amount_minor = models.BigIntegerField(default=0)
    # quantity * unit_amount_minor - discount_amount_minor, computed server-side.
    amount_minor = models.BigIntegerField()

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "finance_invoice_line"
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.invoice}: {self.description}"


class Payment(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="payments")
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payments")
    # Idempotency key (§10/§13 ARCHITECTURE.md) — a retried post with the same
    # reference must not double-post money, enforced by the unique constraint
    # below rather than just application-layer deduping.
    reference = models.CharField(max_length=100)
    amount_minor = models.BigIntegerField()
    currency_code = models.CharField(max_length=3)
    method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default="successful")
    paid_at = models.DateTimeField()

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "finance_payment"
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "reference"], name="uq_payment_organization_reference"
            )
        ]
        ordering = ["-paid_at"]

    def __str__(self) -> str:
        return f"{self.reference} ({self.amount_minor})"


class Refund(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="refunds")
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="refunds")
    amount_minor = models.BigIntegerField()
    currency_code = models.CharField(max_length=3)
    reason = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(max_length=20, choices=REFUND_STATUS_CHOICES, default="completed")
    processed_at = models.DateTimeField()

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "finance_refund"
        ordering = ["-processed_at"]

    def __str__(self) -> str:
        return f"Refund of {self.amount_minor} on {self.payment}"


class Receipt(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="receipts")
    payment = models.OneToOneField(Payment, on_delete=models.PROTECT, related_name="receipt")
    receipt_number = models.CharField(max_length=40)
    status = models.CharField(max_length=20, choices=RECEIPT_STATUS_CHOICES, default="pending")
    file_url = models.CharField(max_length=500, blank=True, default="")
    generated_at = models.DateTimeField(null=True, blank=True)
    error_message = models.CharField(max_length=255, blank=True, default="")

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "finance_receipt"
        constraints = [
            models.UniqueConstraint(fields=["school", "receipt_number"], name="uq_receipt_school_number")
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.receipt_number


class LedgerEntry(BaseModel):
    """Append-only double-entry trail (§18 exit criterion). `ref_type`/
    `ref_id` deliberately aren't a real FK — see the module docstring."""

    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="ledger_entries")
    account = models.CharField(max_length=50)
    debit_minor = models.BigIntegerField(default=0)
    credit_minor = models.BigIntegerField(default=0)
    currency_code = models.CharField(max_length=3)
    ref_type = models.CharField(max_length=20)
    ref_id = models.BigIntegerField()
    description = models.CharField(max_length=255, blank=True, default="")

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "finance_ledger_entry"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["ref_type", "ref_id"])]

    def __str__(self) -> str:
        return f"{self.account}: dr {self.debit_minor} / cr {self.credit_minor}"
