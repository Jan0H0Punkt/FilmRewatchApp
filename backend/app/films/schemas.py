"""Pydantic request/response schemas for the films module (DESIGN §5.3, §5.4).

The M1 PR4 surface: the ``POST /films`` create payload ("log a watched film",
FR-LIB-01..03), the side-effect-free duplicate probe (FR-LIB-05), and the full
§7.3 detail projection returned by ``GET /films/{id}`` and the create.

Everything inherits the strict base (§5.7): unknown fields are rejected and
lossy coercion is refused; the ``Json*`` aliases re-admit the wire form of
types JSON cannot carry natively.

``natural_key`` appears in **no** schema here — it is derived and consumed
server-side only (FR-LIB-04); the client-facing duplicate probe speaks in its
*parts* (primary title, release year, director).
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Self
from urllib.parse import urlsplit

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.core.schemas import JsonDate, JsonDecimal, JsonUUID, StrictSchema
from app.ratings.schemas import RatingEntryRead

_MIN_RELEASE_YEAR = 1888  # REQ §4.1 — the year of the first film ever made.


def _validated_release_year(year: int) -> int:
    """Shared FR-LIB bound: 1888 through the current (UTC) year."""
    current_year = datetime.now(UTC).year
    if not _MIN_RELEASE_YEAR <= year <= current_year:
        raise ValueError(f"release_year must be between {_MIN_RELEASE_YEAR} and {current_year}")
    return year


def _validated_key_part(text: str) -> str:
    """A natural-key text part must not be blank once trimmed (FR-LIB-04)."""
    if not text.strip():
        raise ValueError("must not be blank")
    return text


class TitleCreate(StrictSchema):
    """One title in the create payload (REQ §4.1 Title object).

    Both flags default to ``False`` so a single-title payload can omit them —
    FR-LIB-01 makes a lone title primary automatically (the model validator on
    :class:`FilmCreate` applies that rule).
    """

    value: str = Field(min_length=1, max_length=255)
    is_primary: bool = False
    is_original: bool = False

    @field_validator("value")
    @classmethod
    def _value_not_blank(cls, value: str) -> str:
        return _validated_key_part(value)


class FirstRatingCreate(StrictSchema):
    """The mandatory first rating in the create payload (FR-LIB-03, REQ §4.2)."""

    value: JsonDecimal
    watch_date: JsonDate

    @field_validator("value")
    @classmethod
    def _value_in_half_steps(cls, value: JsonDecimal) -> JsonDecimal:
        # FR-RAT-02 / §5.4: 0.5-5.0 in increments of 0.5.
        if not Decimal("0.5") <= value <= Decimal("5.0") or value % Decimal("0.5") != 0:
            raise ValueError("rating value must be between 0.5 and 5.0 in steps of 0.5")
        return value

    @field_validator("watch_date")
    @classmethod
    def _not_in_the_future(cls, value: JsonDate) -> JsonDate:
        # FR-RAT-03 / §5.4, judged against the server's UTC today.
        if value > datetime.now(UTC).date():
            raise ValueError("watch_date must not be in the future")
        return value


class FilmCreate(StrictSchema):
    """The ``POST /films`` payload — a film plus its first rating (FR-LIB-01..03).

    ``id`` is the §5.5 scoping note: an optional client-minted UUID (server-
    generated when absent). ``is_favorite``/``delay_days`` are deliberately
    **absent** — the system defaults them at create (FR-LIB-02) — as is
    ``natural_key`` (FR-LIB-04); the strict base rejects them as unknown fields.
    """

    id: JsonUUID | None = None
    titles: list[TitleCreate] = Field(min_length=1)
    release_year: int
    director: str = Field(min_length=1, max_length=255)
    genre: list[str] = Field(min_length=1)
    tags: list[str] = Field(min_length=1)
    poster_image: str | None = Field(default=None, max_length=2048)
    first_rating: FirstRatingCreate

    @field_validator("release_year")
    @classmethod
    def _release_year_in_range(cls, year: int) -> int:
        return _validated_release_year(year)

    @field_validator("director")
    @classmethod
    def _director_not_blank(cls, director: str) -> str:
        return _validated_key_part(director)

    @field_validator("poster_image")
    @classmethod
    def _poster_is_a_well_formed_url(cls, url: str | None) -> str | None:
        # FR-LIB-14: well-formed URL, nothing more — no format/file-type checks.
        if url is None:
            return url
        try:
            parts = urlsplit(url)
        except ValueError as error:
            raise ValueError("poster_image must be a well-formed URL") from error
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            raise ValueError("poster_image must be a well-formed http(s) URL")
        return url

    @model_validator(mode="after")
    def _enforce_title_rules(self) -> Self:
        # REQ §4.1 Title rules: a lone title is automatically primary
        # (FR-LIB-01); otherwise exactly one primary; at most one original.
        primaries = [title for title in self.titles if title.is_primary]
        if len(self.titles) == 1 and not primaries:
            self.titles[0].is_primary = True
        elif len(primaries) != 1:
            raise ValueError("exactly one title must be marked primary")
        if sum(1 for title in self.titles if title.is_original) > 1:
            raise ValueError("at most one title may be marked original")
        return self


class DuplicateCheckRequest(StrictSchema):
    """The ``POST /films/duplicate-check`` probe body — natural-key *parts*.

    The same verdict the create applies (FR-LIB-05), answerable while the user
    is still typing; the key itself is never exposed (FR-LIB-04).
    """

    primary_title: str = Field(min_length=1, max_length=255)
    release_year: int
    director: str = Field(min_length=1, max_length=255)

    @field_validator("primary_title", "director")
    @classmethod
    def _part_not_blank(cls, part: str) -> str:
        return _validated_key_part(part)

    @field_validator("release_year")
    @classmethod
    def _release_year_in_range(cls, year: int) -> int:
        return _validated_release_year(year)


class FilmSummary(StrictSchema):
    """Just enough of a film to name it and open it (FR-LIB-05)."""

    id: JsonUUID
    primary_title: str
    release_year: int
    director: str


class DuplicateCheckResult(StrictSchema):
    """The probe's verdict; ``film`` identifies the collision when ``duplicate``."""

    duplicate: bool
    film: FilmSummary | None


class TitleRead(StrictSchema):
    """One title in the detail projection (REQ §4.1 Title object, §7.3)."""

    model_config = ConfigDict(from_attributes=True)

    value: str
    is_primary: bool
    is_original: bool


class FilmDetailRead(StrictSchema):
    """The full §7.3 projection served by ``GET /films/{id}`` and the create.

    ``average_rating`` is computed from the history on every read — arithmetic
    mean of the entry values, one decimal (FR-RAT-09/10, NFR-INT-01) — and
    ``rating_history`` is ordered most recent first (FR-RAT-05/06).
    ``natural_key`` is deliberately absent (FR-LIB-04).
    """

    id: JsonUUID
    titles: list[TitleRead]
    release_year: int
    director: str
    genre: list[str]
    tags: list[str]
    poster_image: str | None
    is_favorite: bool
    delay_days: int
    rating_history: list[RatingEntryRead]
    average_rating: float
    created_at: datetime
    updated_at: datetime
