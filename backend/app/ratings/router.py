"""Presentation layer for the ratings module (DESIGN §5.1, M1 PR7).

FastAPI routes under ``/api/v1/ratings/*``: ``DELETE /{id}``, the last-rating
half of the FR-RAT-07 rule. This route depends on ``FilmService`` (the films
module's dependencies), not this module's own ``RatingService`` — the
last-rating-deletes-the-film case must call back into ``FilmService.delete``,
and ``FilmService`` already depends on ``RatingService`` for the create/add
flows, so the reverse direction would be a circular service dependency (see
``app/films/service.py``'s docstring). ``POST /films/{id}/ratings`` (adding a
rating) is consequently defined on the films router, not here.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.films.dependencies import get_film_service
from app.films.service import FilmService
from app.ratings.schemas import RatingDeletionResult

router = APIRouter()


@router.delete(
    "/{rating_id}",
    summary="Delete a rating",
    description=(
        "Deletes one rating entry (FR-RAT-07). If it was the film's **last** "
        "remaining rating, the whole film is deleted with it — atomically, "
        "cascading and reaping orphaned labels exactly as `DELETE /films/{id}` "
        "does — since the library only holds watched films. `film_deleted` in "
        "the response tells the two outcomes apart. There is deliberately no "
        "`PATCH`/`PUT` route for ratings (FR-RAT-08): corrections are "
        "delete-then-recreate. An unknown rating id yields `NOT_FOUND`."
    ),
)
def delete_rating(
    rating_id: UUID,
    service: Annotated[FilmService, Depends(get_film_service)],
) -> RatingDeletionResult:
    return service.delete_rating(rating_id)
