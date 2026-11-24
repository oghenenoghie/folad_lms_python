"""Domain errors — surfaced by views.py as a 409/400."""


class AssignmentError(Exception):
    pass


class InvalidSubmission(AssignmentError):
    pass
