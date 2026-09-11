"""Presentation layer for the films module (DESIGN §5.1, M1 PR4/PR5/PR6).

FastAPI routes under ``/api/v1/films`` (mounted by the app factory): the
"log a watched film" create (FR-LIB-01..05), the side-effect-free duplicate
probe (FR-LIB-05), the §7.3 detail read, the edit (FR-LIB-06..09), and the
cascading delete (FR-LIB-10..12). Routing and (de)serialisation only — every
rule lives in the service layer (NFR-MAINT-02).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.films.dependencies import get_film_service
from app.films.schemas import (
    DuplicateCheckRequest,
    DuplicateCheckResult,
    FilmCreate,
    FilmDetailRead,
    FilmUpdate,
)
from app.films.service import FilmService

router = APIRouter()


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Log a watched film",
    description=(
        "Creates a film **together with** its mandatory first rating, tags, and "
        "genres in one atomic operation (FR-LIB-01..03) — the library only holds "
        "watched films. A film duplicating an existing one (same primary title, "
        "release year, and director — case/whitespace-insensitive) is rejected "
        "with the `DUPLICATE_FILM` error identifying the existing film (FR-LIB-05)."
    ),
)
def create_film(
    payload: FilmCreate,
    service: Annotated[FilmService, Depends(get_film_service)],
) -> FilmDetailRead:
    return service.create(payload)


@router.post(
    "/duplicate-check",
    summary="Probe for a duplicate film",
    description=(
        "Side-effect-free duplicate check by natural-key parts — the background "
        "probe run while the user fills in the create form (FR-LIB-05). Returns "
        "the same verdict the create would apply, without creating anything."
    ),
)
def check_duplicate(
    payload: DuplicateCheckRequest,
    service: Annotated[FilmService, Depends(get_film_service)],
) -> DuplicateCheckResult:
    return service.check_duplicate(payload.primary_title, payload.release_year, payload.director)


@router.get(
    "/{film_id}",
    summary="Fetch one film",
    description=(
        "The full §7.3 projection: titles, genres, tags, rating history (most "
        "recent first) and the `average_rating` computed from that history on "
        "every read — never stored, never stale (FR-RAT-05/06/09, NFR-INT-01)."
    ),
)
def get_film(
    film_id: UUID,
    service: Annotated[FilmService, Depends(get_film_service)],
) -> FilmDetailRead:
    return service.get_detail(film_id)


@router.patch(
    "/{film_id}",
    summary="Edit a film",
    description=(
        "Edits the user-editable fields of a film — titles, release year, "
        "director, genres, tags, poster, favourite flag, rewatch delay "
        "(FR-LIB-06). Every field is optional (absent = unchanged); `id`, "
        "`created_at`, `natural_key`, and `average_rating` are never editable "
        "(FR-LIB-07). Editing the primary title, release year, or director "
        "recomputes `natural_key` (FR-LIB-08); an edit that would collide "
        "with another film is rejected, unapplied, with `DUPLICATE_FILM` "
        "identifying the collision (FR-LIB-09)."
    ),
)
def update_film(
    film_id: UUID,
    payload: FilmUpdate,
    service: Annotated[FilmService, Depends(get_film_service)],
) -> FilmDetailRead:
    return service.update(film_id, payload)


@router.delete(
    "/{film_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a film",
    description=(
        "Deletes a film together with its titles, rating history, and tag/genre "
        "links, atomically (FR-LIB-10..12, NFR-INT-02); any tag or genre the "
        "deletion leaves on no films is deleted too (FR-TAG-04). An unknown id "
        "yields the `NOT_FOUND` envelope."
    ),
)
def delete_film(
    film_id: UUID,
    service: Annotated[FilmService, Depends(get_film_service)],
) -> None:
    service.delete(film_id)
