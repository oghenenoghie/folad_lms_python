"""Domain errors shared across the finance services — all surfaced by views.py
as a 409, same as apps.examinations.services.result_service.InvalidResultTransition.
"""


class FinanceError(Exception):
    pass


class InvalidInvoiceState(FinanceError):
    pass


class InvalidPaymentAmount(FinanceError):
    pass


class InvalidRefundAmount(FinanceError):
    pass
