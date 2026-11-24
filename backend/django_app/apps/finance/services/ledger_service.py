"""Double-entry posting helper (§18 exit criterion: append-only ledger).
Every call writes exactly two balanced LedgerEntry rows — one debit, one
credit, same amount — inside the caller's existing transaction; nothing
here opens its own atomic() block, since a ledger post is never meaningful
on its own, only as part of the invoice/payment/refund write that causes it.
"""
from apps.finance.models import LedgerEntry

ACCOUNT_ACCOUNTS_RECEIVABLE = "accounts_receivable"
ACCOUNT_REVENUE = "revenue"
ACCOUNT_CASH = "cash"


def post_double_entry(
    *, organization, school, currency_code, debit_account: str, credit_account: str,
    amount_minor: int, ref_type: str, ref_id: int, description: str, actor,
) -> tuple[LedgerEntry, LedgerEntry]:
    debit = LedgerEntry.objects.create(
        organization=organization,
        school=school,
        account=debit_account,
        debit_minor=amount_minor,
        credit_minor=0,
        currency_code=currency_code,
        ref_type=ref_type,
        ref_id=ref_id,
        description=description,
        created_by=actor,
        updated_by=actor,
    )
    credit = LedgerEntry.objects.create(
        organization=organization,
        school=school,
        account=credit_account,
        debit_minor=0,
        credit_minor=amount_minor,
        currency_code=currency_code,
        ref_type=ref_type,
        ref_id=ref_id,
        description=description,
        created_by=actor,
        updated_by=actor,
    )
    return debit, credit
