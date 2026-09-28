"""Pydantic schemas for the letterboxd routes (REQ §5.7)."""

from typing import Annotated

from pydantic import Field

from app.core.schemas import JsonDate, JsonUUID, StrictSchema


class SuggestedFilmRead(StrictSchema):
    """The film the sync matched (FR-LBX-04), by its primary title."""

    id: JsonUUID
    title: str


class LetterboxdEntryRead(StrictSchema):
    """One open review-list entry."""

    id: JsonUUID
    film_title: str
    film_year: int
    film_url: str
    watched_date: JsonDate
    # A JSON number like ``RatingEntryRead.value``; null = unrated (FR-LBX-08).
    rating: Annotated[float, Field(strict=False)] | None
    rewatch: bool
    suggested_film: SuggestedFilmRead | None


class AssignBody(StrictSchema):
    """The film to add the entry's watch to — the suggestion or another one (FR-LBX-06)."""

    film_id: JsonUUID


class SyncResult(StrictSchema):
    """How many entries a manual sync queued."""

    queued: int
