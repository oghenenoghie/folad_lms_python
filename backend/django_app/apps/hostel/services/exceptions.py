"""Domain errors — surfaced by views.py as a 409."""


class HostelError(Exception):
    pass


class BedNotAvailable(HostelError):
    pass
