"""The standard response envelope used across every /api/v1 endpoint (§9
ARCHITECTURE.md)."""
from rest_framework.response import Response


def envelope(data=None, *, message: str = "Operation completed successfully", success: bool = True,
             errors: list | None = None, status: int = 200) -> Response:
    return Response(
        {"success": success, "data": data or {}, "message": message, "errors": errors or []},
        status=status,
    )


def error_envelope(message: str, *, errors: list | None = None, status: int = 400) -> Response:
    return envelope(data={}, message=message, success=False, errors=errors or [message], status=status)
