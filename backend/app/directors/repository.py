"""Data-access layer for the directors module (DESIGN §5.1).

CRUD over the SQLAlchemy ORM behind a stable interface; no business rules, no
HTTP. Directors are modelled like tags and genres (REQ §4.1), so this mirrors
``app/genres/repository.py`` — the service depends on the
:class:`~app.directors.service.DirectorRepositoryProtocol` interface, which this
class satisfies structurally.

Transaction control stays with the caller: nothing here commits. The film flows
call :meth:`DirectorRepository.get_or_create` / :meth:`delete_orphans` inside
their own atomic unit of work.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import CursorResult, delete, exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.directors.models import Director, FilmDirector


class DirectorRepository:
    """SQLAlchemy-backed director data access (one instance per request session)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_or_create(self, name: str) -> Director:
        """Return the director named ``name`` (case-insensitively), creating it if new.

        Dedupe is case-insensitive: looking up ``"michael mann"`` returns an
        existing ``"Michael Mann"`` row with its original casing preserved. The
        insert runs inside a SAVEPOINT (``begin_nested``) so a concurrent
        creator racing us to the unique ``lower(name)`` index only rolls back
        the savepoint — never the caller's enclosing transaction (the film
        flows' atomicity, NFR-INT-02) — after which the winner's row is fetched
        and returned.
        """
        existing = self.find_by_name(name)
        if existing is not None:
            return existing
        try:
            with self._session.begin_nested():
                created = Director(name=name)
                self._session.add(created)
            return created
        except IntegrityError:
            # Lost the race: the unique index blocked us until the concurrent
            # transaction committed, so a fresh lookup now sees its row.
            won = self.find_by_name(name)
            if won is None:
                raise
            return won

    def find_by_name(self, name: str) -> Director | None:
        """Case-insensitive lookup via the ``lower(name)`` unique index (§5.2)."""
        statement = select(Director).where(func.lower(Director.name) == func.lower(name))
        return self._session.scalars(statement).one_or_none()

    def delete_orphans(self) -> int:
        """Delete every director with no remaining film links; return the count.

        The FR-TAG-04-analogue orphan-cleanup primitive: a director never exists
        standalone, so the film flows call this after unlinking. Directors still
        credited on at least one film are untouched.
        """
        statement = delete(Director).where(
            ~exists(select(FilmDirector.director_id).where(FilmDirector.director_id == Director.id))
        )
        result = self._session.execute(statement)
        # A DML statement always yields a CursorResult; the narrowing gives the
        # checker the ``rowcount`` attribute Result[Any] hides.
        assert isinstance(result, CursorResult)
        return result.rowcount

    def link_film(self, film_id: uuid.UUID, director_id: uuid.UUID, position: int) -> None:
        """Credit a director on a film at ``position`` via the join row.

        No ``ON CONFLICT`` clause, unlike the label tables: the film flows
        always :meth:`unlink_all` first and re-credit the whole list, so a
        duplicate link here would mean the caller staged the same director
        twice — a bug worth surfacing, not absorbing.
        """
        self._session.add(FilmDirector(film_id=film_id, director_id=director_id, position=position))

    def unlink_all(self, film_id: uuid.UUID) -> None:
        """Drop every director link of one film (the credit list's replacement).

        Runs immediately as a Core DELETE rather than through the unit of work,
        so the replacement links never race the rows they replace on the join
        table's composite primary key. The director rows themselves are
        untouched — whether they survive is :meth:`delete_orphans`' question,
        asked by the film flows afterwards.
        """
        self._session.execute(delete(FilmDirector).where(FilmDirector.film_id == film_id))

    def list_for_film(self, film_id: uuid.UUID) -> Sequence[Director]:
        """One film's directors, in credited order (the §7.3 projection).

        Ordered by the join row's ``position``, not alphabetically — this is
        where directors part ways with tags and genres.
        """
        statement = (
            select(Director)
            .join(FilmDirector, FilmDirector.director_id == Director.id)
            .where(FilmDirector.film_id == film_id)
            .order_by(FilmDirector.position)
        )
        return self._session.scalars(statement).all()
