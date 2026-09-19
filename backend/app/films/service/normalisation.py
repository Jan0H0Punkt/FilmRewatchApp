"""How the service normalises free text before it becomes identity or a link.

Both helpers apply the same notion — trimmed, lowercased — that the store
itself is unique under, so the pre-checks here agree with the database.
"""

from collections.abc import Sequence


def derive_natural_key(primary_title: str, release_year: int, director: str) -> str:
    """The FR-LIB-04 derivation — duplicate detection's whole identity notion.

    ``lowercase(trim(primary_title))|release_year|lowercase(trim(director))``:
    case- and surrounding-whitespace-insensitive on the text parts (REQ §4.1
    note). Derived and consumed server-side only; never in a schema.
    """
    return f"{primary_title.strip().lower()}|{release_year}|{director.strip().lower()}"


def deduplicated(names: Sequence[str]) -> list[str]:
    """Payload labels deduplicated the way the store is unique: trimmed,
    case-insensitively, first spelling wins — so ``["Drama", "drama"]`` links
    one row once instead of tripping the join table's primary key."""
    seen: set[str] = set()
    unique: list[str] = []
    for name in names:
        key = name.strip().lower()
        if key not in seen:
            seen.add(key)
            unique.append(name)
    return unique
