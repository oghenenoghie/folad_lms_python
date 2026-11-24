"""Domain errors — surfaced by views.py as a 409."""


class TransportError(Exception):
    pass


class VehicleAtCapacity(TransportError):
    pass
