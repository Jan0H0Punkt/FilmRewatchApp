"""Data-access layer for the genres module (DESIGN §5.1, M1 PR3).

CRUD over the SQLAlchemy ORM behind a stable interface; no business rules, no
HTTP. Genres are modelled identically to tags (REQ §4.4), so this mirrors
``app/tags/repository.py`` — the service depends on the
:class:`~app.genres.service.GenreRepositoryProtocol` interface, which this
class satisfies structurally.

Transaction control stays with the caller: nothing here commits. The film flows
(M1 PR4+) call :meth:`GenreRepository.get_or_create` / :meth:`delete_orphans`
inside their own atomic unit of work; the lookup route only reads.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import CursorResult, delete, exists, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.genres.models import FilmGenre, Genre


def _escape_like(value: str) -> str:
    """Escape ``%``/``_``/``\\`` so a prefix matches literally in ``LIKE``."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class GenreRepository:
    """SQLAlchemy-backed genre data access (one instance per request session)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_or_create(self, name: str) -> Genre:
        """Return the genre named ``name`` (case-insensitively), creating it if new.

        Dedupe is case-insensitive (FR-TAG-02 analogue): looking up ``"tHrIlLeR"``
        returns an existing ``"Thriller"`` row with its original casing preserved.
        The insert runs inside a SAVEPOINT (``begin_nested``) so a concurrent
        creator racing us to the unique ``lower(name)`` index only rolls back the
        savepoint — never the caller's enclosing transaction (the film flows'
        atomicity, NFR-INT-02) — after which the winner's row is fetched and
        returned.
        """
        existing = self.find_by_name(name)
        if existing is not None:
            return existing
        try:
            with self._session.begin_nested():
                created = Genre(name=name)
                self._session.add(created)
            return created
        except IntegrityError:
            # Lost the race: the unique index blocked us until the concurrent
            # transaction committed, so a fresh lookup now sees its row.
            won = self.find_by_name(name)
            if won is None:
                raise
            return won

    def list_by_prefix(self, prefix: str | None = None) -> Sequence[Genre]:
        """List genres alphabetically, optionally filtered by case-insensitive prefix.

        Backs the ``GET /genres?prefix=`` autocomplete lookup (FR-TAG-06
        analogue). LIKE wildcards in ``prefix`` are escaped, so ``100%`` only
        matches labels that literally start with ``100%``.
        """
        statement = select(Genre).order_by(func.lower(Genre.name))
        if prefix:
            statement = statement.where(Genre.name.ilike(_escape_like(prefix) + "%", escape="\\"))
        return self._session.scalars(statement).all()

    def delete_orphans(self) -> int:
        """Delete every genre with no remaining film links; return the count.

        The FR-TAG-04-analogue orphan-cleanup primitive: a genre never exists
        standalone, so the film flows (M1 PR5/PR6/PR7) call this after
        unlinking. Shared labels — any row with at least one ``film_genres``
        link — are untouched.
        """
        statement = delete(Genre).where(
            ~exists(select(FilmGenre.genre_id).where(FilmGenre.genre_id == Genre.id))
        )
        result = self._session.execute(statement)
        # A DML statement always yields a CursorResult; the narrowing gives the
        # checker the ``rowcount`` attribute Result[Any] hides.
        assert isinstance(result, CursorResult)
        return result.rowcount

    def find_by_name(self, name: str) -> Genre | None:
        """Case-insensitive lookup via the ``lower(name)`` unique index (§5.2)."""
        statement = select(Genre).where(func.lower(Genre.name) == func.lower(name))
        return self._session.scalars(statement).one_or_none()

    def link_film(self, film_id: uuid.UUID, genre_id: uuid.UUID) -> None:
        """Associate a genre with a film via the ``film_genres`` join row.

        ``ON CONFLICT DO NOTHING`` on the composite primary key makes assigning
        an already-present link a no-op (§5.5 natural idempotency) instead of a
        constraint violation.
        """
        statement = (
            insert(FilmGenre)
            .values(film_id=film_id, genre_id=genre_id)
            .on_conflict_do_nothing(index_elements=[FilmGenre.film_id, FilmGenre.genre_id])
        )
        self._session.execute(statement)

    def list_for_film(self, film_id: uuid.UUID) -> Sequence[Genre]:
        """The genres assigned to one film, alphabetically (the §7.3 projection)."""
        statement = (
            select(Genre)
            .join(FilmGenre, FilmGenre.genre_id == Genre.id)
            .where(FilmGenre.film_id == film_id)
            .order_by(func.lower(Genre.name))
        )
        return self._session.scalars(statement).all()
