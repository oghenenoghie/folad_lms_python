"""Auto-generates the "code"-shaped identifiers a model would otherwise
require an admin/operator to type by hand — a Model.save() override calling
one of these (see e.g. apps.academics.models.Subject) is the one place that
covers every creation path (a service, the API, Django Admin, a shell,
a factory) alike, since all of them eventually call Model.save(). Never
overrides a value the caller already supplied.
"""
import re


def next_sequence_code(*, queryset, field_name: str, prefix: str = "", width: int = 4) -> str:
    """The next "<prefix><zero-padded-number>" not yet used by `queryset`
    (already scoped to whatever the value must be unique within — e.g. one
    school), e.g. "INV-0007". Scans existing values for the highest numeric
    suffix under `prefix` and increments it; starts at 1 if none exist yet
    or none parse as "<prefix><digits>".
    """
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
    max_n = 0
    for value in queryset.values_list(field_name, flat=True):
        match = pattern.match(value or "")
        if match:
            max_n = max(max_n, int(match.group(1)))
    return f"{prefix}{max_n + 1:0{width}d}"


def next_abbreviation_code(*, queryset, field_name: str, name: str, length: int = 3) -> str:
    """A short, human-readable code derived from `name` (e.g. "MAT" for
    "Mathematics"), unique within `queryset` (already scoped to whatever
    the value must be unique within). Appends a numeric suffix on
    collision (MAT2, MAT3, ...) rather than a code nobody would recognize.
    """
    letters = re.sub(r"[^A-Za-z]", "", name).upper()
    base = letters[:length] or "GEN"
    existing = set(queryset.values_list(field_name, flat=True))
    if base not in existing:
        return base
    suffix = 2
    while f"{base}{suffix}" in existing:
        suffix += 1
    return f"{base}{suffix}"
