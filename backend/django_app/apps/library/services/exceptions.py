"""Domain errors — surfaced by views.py as a 409, same as
apps.examinations.services.result_service.InvalidResultTransition.
"""


class LibraryError(Exception):
    pass


class CopyNotAvailable(LibraryError):
    pass


class InvalidLoanState(LibraryError):
    pass
