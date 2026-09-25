"""Stats data access against a real Postgres (DESIGN §9). ``db_session`` auto-marks these ``db``."""

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.films.models import Film, Title
from app.genres.models import FilmGenre, Genre
from app.ratings.models import RatingEntry
from app.ratings.service import EARLIER_WATCH_DATE
from app.stats.repository import StatsRepository


def test_watches_joins_primary_title_and_genres_and_undates_the_sentinel(
    db_session: Session,
) -> None:
    film = Film(
        natural_key="heat|1995|michael mann",
        release_year=1995,
        director="Michael Mann",
        runtime_minutes=170,
    )
    db_session.add(film)
    db_session.flush()
    db_session.add(Title(film_id=film.id, value="Heat", is_primary=True, is_original=True))
    db_session.add(Title(film_id=film.id, value="Heat (alt)", is_primary=False, is_original=False))
    crime, thriller = Genre(name="Crime"), Genre(name="Thriller")
    db_session.add_all([crime, thriller])
    db_session.flush()
    db_session.add_all(
        [
            FilmGenre(film_id=film.id, genre_id=thriller.id, position=1),
            FilmGenre(film_id=film.id, genre_id=crime.id, position=0),
            RatingEntry(film_id=film.id, value=Decimal("4.5"), watch_date=date(2026, 3, 1)),
            RatingEntry(film_id=film.id, value=None, watch_date=EARLIER_WATCH_DATE),
        ]
    )
    db_session.commit()

    watches = sorted(StatsRepository(db_session).watches(), key=lambda w: w.watch_date is None)

    assert [w.watch_date for w in watches] == [date(2026, 3, 1), None]
    assert {w.title for w in watches} == {"Heat"}
    assert watches[0].genres == ("Crime", "Thriller")
    assert watches[0].value == Decimal("4.5")
