"""Data-access layer for the tags module (DESIGN §5.1, M1 PR3).

CRUD over the SQLAlchemy ORM behind a stable interface; no business rules, no
HTTP. The service depends on the :class:`~app.tags.service.TagRepositoryProtocol`
interface, which this class satisfies structurally.

Transaction control stays with the caller: nothing here commits. The film flows
(M1 PR4+) call :meth:`TagRepository.get_or_create` / :meth:`delete_orphans`
inside their own atomic unit of work; the lookup route only reads.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import CursorResult, delete, exists, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.tags.models import FilmTag, Tag


def _escape_like(value: str) -> str:
    """Escape ``%``/``_``/``\\`` so a prefix matches literally in ``LIKE``."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class TagRepository:
    """SQLAlchemy-backed tag data access (one instance per request session)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_or_create(self, name: str) -> Tag:
        """Return the tag named ``name`` (case-insensitively), creating it if new.

        Dedupe is case-insensitive (FR-TAG-02): looking up ``"dRaMa"`` returns an
        existing ``"Drama"`` row with its original casing preserved. The insert
        runs inside a SAVEPOINT (``begin_nested``) so a concurrent creator racing
        us to the unique ``lower(name)`` index only rolls back the savepoint —
        never the caller's enclosing transaction (the film flows' atomicity,
        NFR-INT-02) — after which the winner's row is fetched and returned.
        """
        existing = self.find_by_name(name)
        if existing is not None:
            return existing
        try:
            with self._session.begin_nested():
                created = Tag(name=name)
                self._session.add(created)
            return created
        except IntegrityError:
            # Lost the race: the unique index blocked us until the concurrent
            # transaction committed, so a fresh lookup now sees its row.
            won = self.find_by_name(name)
            if won is None:
                raise
            return won

    def list_by_prefix(self, prefix: str | None = None) -> Sequence[Tag]:
        """List tags alphabetically, optionally filtered by case-insensitive prefix.

        Backs the ``GET /tags?prefix=`` autocomplete lookup (FR-TAG-06). LIKE
        wildcards in ``prefix`` are escaped, so ``100%`` only matches labels that
        literally start with ``100%``.
        """
        statement = select(Tag).order_by(func.lower(Tag.name))
        if prefix:
            statement = statement.where(Tag.name.ilike(_escape_like(prefix) + "%", escape="\\"))
        return self._session.scalars(statement).all()

    def delete_orphans(self) -> int:
        """Delete every tag with no remaining film links; return the count.

        The FR-TAG-04 orphan-cleanup primitive: a tag never exists standalone,
        so the film flows (M1 PR5/PR6/PR7) call this after unlinking. Shared
        labels — any row with at least one ``film_tags`` link — are untouched.
        """
        statement = delete(Tag).where(
            ~exists(select(FilmTag.tag_id).where(FilmTag.tag_id == Tag.id))
        )
        result = self._session.execute(statement)
        # A DML statement always yields a CursorResult; the narrowing gives the
        # checker the ``rowcount`` attribute Result[Any] hides.
        assert isinstance(result, CursorResult)
        return result.rowcount

    def find_by_name(self, name: str) -> Tag | None:
        """Case-insensitive lookup via the ``lower(name)`` unique index (§5.2)."""
        statement = select(Tag).where(func.lower(Tag.name) == func.lower(name))
        return self._session.scalars(statement).one_or_none()

    def link_film(self, film_id: uuid.UUID, tag_id: uuid.UUID) -> None:
        """Associate a tag with a film via the ``film_tags`` join row (FR-TAG-03).

        ``ON CONFLICT DO NOTHING`` on the composite primary key makes assigning
        an already-present link a no-op (§5.5 natural idempotency) instead of a
        constraint violation.
        """
        statement = (
            insert(FilmTag)
            .values(film_id=film_id, tag_id=tag_id)
            .on_conflict_do_nothing(index_elements=[FilmTag.film_id, FilmTag.tag_id])
        )
        self._session.execute(statement)

    def unlink_film(self, film_id: uuid.UUID, tag_id: uuid.UUID) -> None:
        """Remove a tag's ``film_tags`` link to a film (FR-TAG-04, M1 PR5).

        Deleting an absent link is a no-op, mirroring :meth:`link_film`'s
        idempotency. The tag row itself is untouched — whether it survives is
        :meth:`delete_orphans`' question, asked by the film flows afterwards.
        """
        statement = delete(FilmTag).where(FilmTag.film_id == film_id, FilmTag.tag_id == tag_id)
        self._session.execute(statement)

    def list_for_film(self, film_id: uuid.UUID) -> Sequence[Tag]:
        """The tags assigned to one film, alphabetically (the §7.3 projection)."""
        statement = (
            select(Tag)
            .join(FilmTag, FilmTag.tag_id == Tag.id)
            .where(FilmTag.film_id == film_id)
            .order_by(func.lower(Tag.name))
        )
        return self._session.scalars(statement).all()
