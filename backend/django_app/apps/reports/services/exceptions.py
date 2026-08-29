"""Domain errors — surfaced by views.py as a 400."""


class ReportError(Exception):
    pass


class UnknownReportType(ReportError):
    pass
