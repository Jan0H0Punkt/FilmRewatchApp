"""Pydantic response schemas for the stats module (DESIGN §5.3).

Read-only. Built from the algorithm's dataclasses via ``from_attributes``; the
lists are ``list`` because strict mode rejects a tuple for a list field.
"""

from uuid import UUID

from pydantic import ConfigDict

from app.core.schemas import StrictSchema
from app.stats.algorithm import Stats


class _Read(StrictSchema):
    model_config = ConfigDict(from_attributes=True)


class TopNameRead(_Read):
    name: str
    watches: int
    average_rating: float
    score: float


class TopFilmRead(_Read):
    film_id: UUID
    title: str
    watches: int
    average_rating: float
    score: float


class RatingCountRead(_Read):
    value: float
    count: int


class BucketRead(_Read):
    label: str
    count: int


class StatsBlockRead(_Read):
    watches: int
    first_watches: int
    rewatches: int
    films_released_that_year: int | None
    distinct_films: int
    minutes_watched: int
    average_rating: float | None
    rating_distribution: list[RatingCountRead]
    top_genres: list[TopNameRead]
    top_directors: list[TopNameRead]
    top_tags: list[TopNameRead]
    top_films: list[TopFilmRead]
    buckets: list[BucketRead]


class YearStatsRead(StatsBlockRead):
    year: int


class StatsRead(_Read):
    total: StatsBlockRead
    years: list[YearStatsRead]

    @classmethod
    def from_stats(cls, stats: Stats) -> "StatsRead":
        """Flattens each ``YearStats`` into its block plus ``year``, the wire shape."""
        return cls(
            total=StatsBlockRead.model_validate(stats.total),
            years=[
                YearStatsRead.model_validate(
                    {"year": y.year, **StatsBlockRead.model_validate(y.block).model_dump()}
                )
                for y in stats.years
            ],
        )
