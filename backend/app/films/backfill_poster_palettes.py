"""One-off backfill for ``films.poster_palette`` (FR-LIB-13/14).

Migration 0010 adds the column nullable with no default, so every film that
existed before it has ``poster_palette IS NULL`` even though it has a poster.
This computes and stores it for those rows, exactly the way
:class:`~app.films.service.FilmService` does for a new/edited poster — it
just does not go through the service, since none of the atomicity or
duplicate-detection rules it enforces apply here.

Run from ``backend/``::

    uv run python -m app.films.backfill_poster_palettes          # NULL rows only
    uv run python -m app.films.backfill_poster_palettes --all    # recompute every film with a poster
"""

import argparse

from sqlalchemy import select

from app.core.db import session_scope
from app.films.models import Film
from app.films.service.poster_palette import palette_from_url


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all",
        action="store_true",
        help="recompute poster_palette for every film with a poster, not only NULL rows "
        "(e.g. after a seed-palette algorithm change)",
    )
    args = parser.parse_args()

    with session_scope() as session:
        conditions = [Film.poster_image.is_not(None)]
        if not args.all:
            conditions.append(Film.poster_palette.is_(None))
        statement = select(Film).where(*conditions)
        films = session.scalars(statement).all()
        updated = 0
        for film in films:
            assert film.poster_image is not None  # the where clause guarantees this
            palette = palette_from_url(film.poster_image)
            if palette is not None:
                film.poster_palette = palette
                updated += 1
        session.commit()
    print(f"Backfilled poster_palette for {updated} of {len(films)} film(s) with a poster.")


if __name__ == "__main__":
    main()
