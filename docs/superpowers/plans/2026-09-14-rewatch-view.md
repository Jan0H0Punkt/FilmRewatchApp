# Rewatch View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the M4 rewatch vertical — a backend engine that computes and stores a daily due-list, an endpoint that serves it, and an Angular view that renders it — plus the §6.5 navigation that makes the app's two destinations reachable.

**Architecture:** The scoring algorithm is a pure, stdlib-only module with no `app.*` imports; a service assembles its FR-RW-02 input from one aggregate query, hands it the list, and persists the ordered result into a `rewatch_suggestions` projection. An in-process asyncio task recomputes daily. `GET /api/v1/rewatch-suggestions` serves the stored rows verbatim, carrying no film metadata — the client already holds the library and joins locally.

**Tech Stack:** FastAPI · SQLAlchemy 2.x · Alembic · pydantic-settings · pytest · pyright strict · Ruff — Angular 22 (standalone, zoneless, signals) · Angular Material M3 · vitest · strict TypeScript

**Spec:** `docs/superpowers/specs/2026-09-14-rewatch-view-design.md`

## Global Constraints

- **Backend gate**, run from `backend/`, must be clean before any task is considered done: `make typecheck` (pyright strict, zero errors), `make lint`, `make format-check`, `make test`. Never hand-format — run `make format`.
- **Frontend gate**, run from `frontend/`: `npm run build` (includes strict TS + `strictTemplates`), `npm test`, `npm run lint`. Template a11y findings are lint errors.
- Everything backend runs through `uv run` / `make`. Never `pip install`. Python is `python3.14`.
- **Do not commit.** Every task ends with the gate green and the working tree dirty. The repo owner reviews the diff and commits.
- Backend layering per feature module: `router → service → repository`, injected via `dependencies.py`. A router never imports a repository. Nothing in a repository commits except its own `commit()` method, which the service calls.
- Every request/response schema inherits `app.core.schemas.StrictSchema`. For `date`/`datetime`/`UUID` **request** fields use the `JsonDate`/`JsonDateTime`/`JsonUUID` aliases, never the bare types.
- Frontend layering per §6.1: `views/*` call facades only, never `api.ts`. DTOs are snake_case and stay inside `api.ts` + `mapper.ts`; everything above sees camelCase.
- Prefer an Angular Material component over hand-rolled markup. Material appearance defaults (`outlined` cards/buttons, `outline` form fields) are global in `app.config.ts` — do not repeat them per instance.
- Docstrings and comments cite design sections and requirement IDs (`§5.8`, `FR-RW-04`) as pointers, not paraphrases. Follow the `code-docs` skill: a one-line summary unless there is a *why* worth writing.
- Colours come from Material M3 system variables (`var(--mat-sys-*)`), which resolve per `color-scheme` — light/dark needs no rule of its own.

---

## File Structure

**Backend — `backend/app/rewatch/`** (all five existing files are docstring-only M0 stubs)

| File | Responsibility |
| --- | --- |
| `algorithm.py` **new** | Pure scoring. Stdlib only — no `app.*`, no SQLAlchemy, no FastAPI. |
| `models.py` | The `rewatch_suggestions` ORM table. |
| `repository.py` | The FR-RW-02 aggregate read, whole-list replace, ordered read, `commit()`. |
| `service.py` | `recompute()` and `list_suggestions()`. Unaware of what triggers it. |
| `dependencies.py` **new** | session → repository → service wiring. |
| `schemas.py` | `RewatchSuggestionRead`. |
| `router.py` | `GET /rewatch-suggestions`. |
| `scheduler.py` **new** | The lifespan-owned daily task. |

Also: `backend/migrations/versions/0006_rewatch_suggestions.py`, `backend/app/core/db.py` (+`session_scope`), `backend/app/core/config.py` (+ one setting), `backend/app/main.py` (lifespan, docstring, version), `backend/.env.example`.

**Frontend**

| File | Responsibility |
| --- | --- |
| `src/app/shared/rating-stars.ts` **new** | `ratingStars()` / `ratingLabel()`, extracted from `library.ts` so both views share one rule. |
| `src/app/domain/rewatch/api.ts` **new** | `RewatchSuggestionDto`, the `httpResource`. |
| `src/app/domain/rewatch/model.ts` **new** | `RewatchSuggestion`, `RewatchCardVm`. |
| `src/app/domain/rewatch/mapper.ts` **new** | DTO → domain, `dueLabel()`, `toRewatchCardVm()`. |
| `src/app/domain/rewatch/facade.ts` **new** | The join, the four states, `removeFilm()`. |
| `src/app/views/rewatch/rewatch.{ts,html,scss}` **new** | The §7.1 card grid. |
| `src/app/core/route-registry.ts` | `navIcon`/`navLabel` + `navDestinations()`. |
| `src/app/core/routes.registry.ts` | Rewatch takes `''`, both destinations get nav fields. |
| `src/app/app.{html,scss,ts,spec.ts}` | The §6.5 navigation element. |
| `src/app/domain/rating/facade.ts` | The optimistic-removal call. |

---

## Deviations from the spec (both deliberate, both already reasoned)

1. **Algorithm dataclass names.** The spec sketched the algorithm's output as `RewatchSuggestion`, which would collide with the ORM class of the same name. The pure module uses `RewatchInput` and **`DueFilm`**; the ORM keeps `RewatchSuggestion`, matching this repo's entity-named-model convention (`Film`, `Title`, `RatingEntry`).
2. **Navigation is CSS, not `mat-sidenav`.** The spec named `mat-sidenav mode="side"`. A drawer that is permanently open and never toggles is a static sidebar; `mat-sidenav` would add a container, a JS breakpoint observer, and a `mode` binding to render the same thing. One `<nav>` styled by a `min-width: 900px` media query produces identical semantics and markup with no JS. Flagged to the repo owner at handoff.

---

## Task 1: The pure algorithm

**Files:**
- Create: `backend/app/rewatch/algorithm.py`
- Create: `backend/tests/test_rewatch_algorithm.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `RewatchInput(film_id: UUID, average_rating: Decimal | None, watch_count: int, last_watched_date: date, is_favorite: bool, delay_days: int)`; `DueFilm(film_id: UUID, days_until_next_rewatch: int)`; `suggest(inputs: Sequence[RewatchInput], today: date) -> list[DueFilm]`; `BASE_INTERVAL_DAYS: int`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_rewatch_algorithm.py`:

```python
"""The pure rewatch algorithm against its FR-RW-03/04 output contract (DESIGN §5.8).

No database and no app fixtures — the module under test imports nothing from
``app``, which is what makes the §3.3 isolation claim checkable.
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.rewatch.algorithm import BASE_INTERVAL_DAYS, DueFilm, RewatchInput, suggest

TODAY = date(2026, 9, 14)


def _input(
    *,
    film_id: uuid.UUID | None = None,
    days_since_watch: int = 0,
    delay_days: int = 0,
    average_rating: Decimal | None = Decimal("4.0"),
    watch_count: int = 1,
    is_favorite: bool = False,
) -> RewatchInput:
    return RewatchInput(
        film_id=film_id or uuid.uuid4(),
        average_rating=average_rating,
        watch_count=watch_count,
        last_watched_date=TODAY - timedelta(days=days_since_watch),
        is_favorite=is_favorite,
        delay_days=delay_days,
    )


def test_a_film_watched_exactly_one_interval_ago_is_due_today() -> None:
    result = suggest([_input(days_since_watch=BASE_INTERVAL_DAYS)], TODAY)
    assert [item.days_until_next_rewatch for item in result] == [0]


def test_a_film_watched_longer_ago_is_overdue_by_the_difference() -> None:
    result = suggest([_input(days_since_watch=BASE_INTERVAL_DAYS + 30)], TODAY)
    assert [item.days_until_next_rewatch for item in result] == [-30]


def test_a_film_not_yet_due_is_omitted_entirely() -> None:
    # FR-RW-03: only films with a value <= 0 are returned.
    assert suggest([_input(days_since_watch=BASE_INTERVAL_DAYS - 1)], TODAY) == []


def test_delay_days_defers_a_film_that_would_otherwise_be_due() -> None:
    assert suggest([_input(days_since_watch=BASE_INTERVAL_DAYS, delay_days=10)], TODAY) == []


def test_delay_days_shortens_how_overdue_a_film_counts_as() -> None:
    result = suggest([_input(days_since_watch=BASE_INTERVAL_DAYS + 30, delay_days=10)], TODAY)
    assert [item.days_until_next_rewatch for item in result] == [-20]


def test_the_most_overdue_film_comes_first() -> None:
    # FR-RW-04: ascending by days_until_next_rewatch, most negative first.
    inputs = [
        _input(days_since_watch=BASE_INTERVAL_DAYS),
        _input(days_since_watch=BASE_INTERVAL_DAYS + 100),
        _input(days_since_watch=BASE_INTERVAL_DAYS + 10),
    ]
    result = suggest(inputs, TODAY)
    assert [item.days_until_next_rewatch for item in result] == [-100, -10, 0]


def test_films_tied_on_days_are_ordered_deterministically() -> None:
    # Two runs over the same data must not reshuffle the view (FR-RW-04).
    first, second = uuid.UUID(int=2), uuid.UUID(int=1)
    inputs = [
        _input(film_id=first, days_since_watch=BASE_INTERVAL_DAYS + 5),
        _input(film_id=second, days_since_watch=BASE_INTERVAL_DAYS + 5),
    ]
    assert suggest(inputs, TODAY) == suggest(list(reversed(inputs)), TODAY)
    assert [item.film_id for item in suggest(inputs, TODAY)] == [second, first]


def test_an_unrated_film_still_gets_a_verdict() -> None:
    # average_rating is null when no watch was rated (FR-RAT-11/12); the
    # algorithm must have a defined behaviour for it, not crash.
    result = suggest(
        [_input(days_since_watch=BASE_INTERVAL_DAYS, average_rating=None)], TODAY
    )
    assert result == [DueFilm(film_id=result[0].film_id, days_until_next_rewatch=0)]


def test_an_empty_library_yields_an_empty_list() -> None:
    assert suggest([], TODAY) == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_rewatch_algorithm.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.rewatch.algorithm'`

- [ ] **Step 3: Write the implementation**

Create `backend/app/rewatch/algorithm.py`:

```python
"""The pure rewatch scoring module (DESIGN §5.8, §3.3, FR-RW-01..04).

Imports nothing from ``app``: no ORM, no HTTP, no session. That isolation is the
point (FR-EXT-09) — replacing the scoring logic means replacing :func:`suggest`'s
body and nothing else, and a sibling algorithm selected by config (FR-EXT-10)
would live beside this file implementing the same signature.

The dataclasses below are the FR-RW-02 input row and the FR-RW-03 output row,
field for field. The names differ from the requirement tables in one place only:
the output is :class:`DueFilm`, because ``RewatchSuggestion`` is taken by the ORM
row in ``models.py`` that stores it.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

# ponytail: placeholder scoring — every film is simply due one year after its
# last watch, deferred by its delay_days. `average_rating`, `watch_count` and
# `is_favorite` are accepted and ignored. The repo owner supplies the real
# formula later; the upgrade path is this module's body, and the signature
# below must not change when it arrives (OPEN_DECISIONS_V1 "M4 — Rewatch
# engine / algorithm internals").
BASE_INTERVAL_DAYS = 365


@dataclass(frozen=True)
class RewatchInput:
    """One film's algorithm input — the FR-RW-02 table, field for field."""

    film_id: UUID
    # ``None`` when no watch of the film was rated (FR-RAT-11/12), which is
    # distinct from a rating of zero — that cannot exist.
    average_rating: Decimal | None
    watch_count: int
    last_watched_date: date
    is_favorite: bool
    delay_days: int


@dataclass(frozen=True)
class DueFilm:
    """One entry of the algorithm's output — the FR-RW-03 table.

    ``days_until_next_rewatch`` is always ``<= 0``: ``0`` is due today, a
    negative value is overdue by that many days.
    """

    film_id: UUID
    days_until_next_rewatch: int


def suggest(inputs: Sequence[RewatchInput], today: date) -> list[DueFilm]:
    """Return the currently-due films, most overdue first (FR-RW-03/04).

    Films that are not yet due are omitted rather than returned with a positive
    value. Ties are broken by film id so two runs over unchanged data produce
    the same order and the view does not reshuffle underneath the user.
    """
    due = [
        DueFilm(film_id=item.film_id, days_until_next_rewatch=days_until)
        for item in inputs
        if (
            days_until := (
                item.last_watched_date
                + timedelta(days=BASE_INTERVAL_DAYS + item.delay_days)
                - today
            ).days
        )
        <= 0
    ]
    due.sort(key=lambda item: (item.days_until_next_rewatch, item.film_id.bytes))
    return due
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_rewatch_algorithm.py -v`
Expected: PASS — 9 passed

- [ ] **Step 5: Run the full backend gate**

Run: `cd backend && make typecheck && make lint && make format-check && make test-offline`
Expected: pyright zero errors, Ruff clean, tests pass.

- [ ] **Step 6: Stop. Do not commit.** Report the files changed and the gate output.

---

## Task 2: The projection table and its migration

**Files:**
- Modify: `backend/app/rewatch/models.py` (replace the whole stub)
- Create: `backend/migrations/versions/0006_rewatch_suggestions.py`
- Modify: `backend/tests/test_db_plumbing.py:13-27`
- Modify: `backend/tests/test_db_harness.py:31-42`

**Interfaces:**
- Consumes: `app.core.db.Base`, `app.core.db.utc_now`.
- Produces: `app.rewatch.models.RewatchSuggestion` — an ORM class with `film_id: uuid.UUID` (PK), `days_until_next_rewatch: int`, `position: int`, `computed_at: datetime`, `__tablename__ = "rewatch_suggestions"`.

- [ ] **Step 1: Write the model**

Replace the entire contents of `backend/app/rewatch/models.py`:

```python
"""The rewatch projection table (DESIGN §5.2, §5.8).

Not a domain entity — the **stored result** of the once-daily job. One row per
currently-due film; the whole table is replaced on every run, never patched.
It is the eighth table, added after the seven §5.2 domain tables.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, utc_now


class RewatchSuggestion(Base):
    """One currently-due film as the last run computed it (FR-RW-03)."""

    __tablename__ = "rewatch_suggestions"

    # One row per due film, so the film id is the natural key — no surrogate.
    # The cascade keeps the projection from outliving a deleted film between
    # daily runs (NFR-INT-02).
    film_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("films.id", ondelete="CASCADE"), primary_key=True
    )
    # Always <= 0 by the FR-RW-03 contract; not a CHECK constraint, because the
    # algorithm — not the database — owns that rule (§5.4).
    days_until_next_rewatch: Mapped[int] = mapped_column(Integer)
    # The algorithm's order, stored rather than re-derived at read time.
    # FR-RW-04 forbids anyone downstream re-sorting, and a future algorithm may
    # order by an internal score whose ties carry meaning that
    # ``days_until_next_rewatch`` alone would lose.
    position: Mapped[int] = mapped_column(Integer)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
```

- [ ] **Step 2: Write the migration**

Create `backend/migrations/versions/0006_rewatch_suggestions.py`:

```python
"""rewatch_suggestions projection (DESIGN §5.2, §5.8)

The stored output of the once-daily rewatch job, served verbatim by
``GET /api/v1/rewatch-suggestions``. Created empty: the first scheduler run
after startup populates it.

Revision ID: 0006_rewatch_suggestions
Revises: 0005_film_genre_position
Create Date: 2026-09-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_rewatch_suggestions"
down_revision: str | None = "0005_film_genre_position"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rewatch_suggestions",
        sa.Column("film_id", sa.Uuid(), nullable=False),
        sa.Column("days_until_next_rewatch", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["film_id"], ["films.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("film_id"),
    )


def downgrade() -> None:
    op.drop_table("rewatch_suggestions")
```

- [ ] **Step 3: Update the two schema guard tests**

Both tests assert an exact table set and will now fail. They are guards, not
obstacles — widen them deliberately.

In `backend/tests/test_db_plumbing.py`, rename the test and extend it:

```python
def test_metadata_defines_exactly_the_seven_domain_tables_plus_the_projection() -> None:
    # One table per entity/join (REQ §4.1-4.5), plus the M4 rewatch projection
    # (§5.8) — and nothing else: a stray model would silently widen the schema.
    # Importing the classes is what registers them on ``Base.metadata``.
    domain_models = (Film, Title, RatingEntry, Tag, FilmTag, Genre, FilmGenre)
    assert {model.__tablename__ for model in domain_models} == {
        "films",
        "titles",
        "rating_entries",
        "tags",
        "film_tags",
        "genres",
        "film_genres",
    }
    assert set(Base.metadata.tables) == {model.__tablename__ for model in domain_models} | {
        RewatchSuggestion.__tablename__
    }
```

Add `from app.rewatch.models import RewatchSuggestion` to that file's imports.

In `backend/tests/test_db_harness.py`, rename `test_migrated_schema_has_the_seven_domain_tables` to `test_migrated_schema_has_the_domain_tables_and_the_projection` and add `"rewatch_suggestions",` to the expected set.

- [ ] **Step 4: Run the migration and confirm autogenerate is empty**

Run:
```bash
cd backend && uv run alembic upgrade head && uv run alembic revision --autogenerate -m "drift check"
```
Expected: the upgrade applies; the generated revision's `upgrade()` body is
empty (just `pass`). **Delete the generated file afterwards** — it exists only
to prove the model and the migration agree.

- [ ] **Step 5: Run the full backend gate**

Run: `cd backend && make typecheck && make lint && make format-check && make test`
Expected: all green, including the two updated guard tests.

- [ ] **Step 6: Stop. Do not commit.**

---

## Task 3: The repository

**Files:**
- Modify: `backend/app/rewatch/repository.py` (replace the whole stub)
- Create: `backend/tests/test_rewatch_repository.py`

**Interfaces:**
- Consumes: Task 1's `RewatchInput`/`DueFilm`; Task 2's `RewatchSuggestion` ORM class.
- Produces: `RewatchRepository(session: Session)` with `collect_inputs() -> list[RewatchInput]`, `replace_all(rows: Sequence[DueFilm], computed_at: datetime) -> None`, `list_all() -> Sequence[RewatchSuggestion]`, `commit() -> None`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_rewatch_repository.py`:

```python
"""Rewatch data access against a real Postgres (DESIGN §9).

The ``db_session`` fixture auto-marks these as ``db``; everything rolls back at
teardown.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.db import utc_now
from app.films.models import Film, Title
from app.ratings.models import RatingEntry
from app.rewatch.algorithm import DueFilm
from app.rewatch.repository import RewatchRepository

COMPUTED_AT: datetime = utc_now()


def _add_film(session: Session, *, natural_key: str, delay_days: int = 0, favorite: bool = False) -> Film:
    film = Film(
        natural_key=natural_key,
        release_year=1995,
        director="Michael Mann",
        runtime_minutes=170,
        poster_image=None,
        is_favorite=favorite,
        delay_days=delay_days,
    )
    session.add(film)
    session.add(Title(film_id=film.id, value=natural_key, is_primary=True, is_original=True))
    return film


def test_collect_inputs_averages_only_the_rated_watches(db_session: Session) -> None:
    film = _add_film(db_session, natural_key="heat|1995|michael mann")
    db_session.add(RatingEntry(film_id=film.id, value=Decimal("4.0"), watch_date=date(2024, 1, 1)))
    db_session.add(RatingEntry(film_id=film.id, value=Decimal("5.0"), watch_date=date(2025, 1, 1)))
    # An unrated watch (FR-RAT-12): it counts as a watch but not toward the mean.
    db_session.add(RatingEntry(film_id=film.id, value=None, watch_date=date(2026, 1, 1)))
    db_session.commit()

    [row] = RewatchRepository(db_session).collect_inputs()

    assert row.film_id == film.id
    assert row.average_rating == Decimal("4.5")
    assert row.watch_count == 3
    assert row.last_watched_date == date(2026, 1, 1)


def test_collect_inputs_reports_a_wholly_unrated_film_as_none(db_session: Session) -> None:
    film = _add_film(db_session, natural_key="solaris|1972|andrei tarkovsky", delay_days=7, favorite=True)
    db_session.add(RatingEntry(film_id=film.id, value=None, watch_date=date(2026, 2, 2)))
    db_session.commit()

    [row] = RewatchRepository(db_session).collect_inputs()

    assert row.average_rating is None
    assert row.watch_count == 1
    assert row.delay_days == 7
    assert row.is_favorite is True


def test_replace_all_stores_the_given_order_as_position(db_session: Session) -> None:
    first = _add_film(db_session, natural_key="a|1990|a")
    second = _add_film(db_session, natural_key="b|1990|b")
    db_session.commit()
    repository = RewatchRepository(db_session)

    repository.replace_all(
        [
            DueFilm(film_id=second.id, days_until_next_rewatch=-40),
            DueFilm(film_id=first.id, days_until_next_rewatch=0),
        ],
        COMPUTED_AT,
    )
    repository.commit()

    stored = list(repository.list_all())
    assert [row.film_id for row in stored] == [second.id, first.id]
    assert [row.position for row in stored] == [0, 1]
    assert [row.days_until_next_rewatch for row in stored] == [-40, 0]


def test_replace_all_leaves_no_rows_from_the_previous_run(db_session: Session) -> None:
    stale = _add_film(db_session, natural_key="stale|1990|a")
    fresh = _add_film(db_session, natural_key="fresh|1990|b")
    db_session.commit()
    repository = RewatchRepository(db_session)

    repository.replace_all([DueFilm(film_id=stale.id, days_until_next_rewatch=-1)], COMPUTED_AT)
    repository.commit()
    repository.replace_all([DueFilm(film_id=fresh.id, days_until_next_rewatch=-2)], COMPUTED_AT)
    repository.commit()

    assert [row.film_id for row in repository.list_all()] == [fresh.id]


def test_an_empty_run_clears_the_projection(db_session: Session) -> None:
    film = _add_film(db_session, natural_key="gone|1990|a")
    db_session.commit()
    repository = RewatchRepository(db_session)
    repository.replace_all([DueFilm(film_id=film.id, days_until_next_rewatch=0)], COMPUTED_AT)
    repository.commit()

    repository.replace_all([], COMPUTED_AT)
    repository.commit()

    assert list(repository.list_all()) == []


def test_deleting_a_film_removes_its_suggestion(db_session: Session) -> None:
    # The FK cascade keeps the projection from outliving the film between runs.
    film = _add_film(db_session, natural_key="doomed|1990|a")
    db_session.commit()
    repository = RewatchRepository(db_session)
    repository.replace_all([DueFilm(film_id=film.id, days_until_next_rewatch=0)], COMPUTED_AT)
    repository.commit()

    db_session.delete(film)
    db_session.commit()

    assert list(repository.list_all()) == []


def test_collect_inputs_is_empty_for_an_empty_library(db_session: Session) -> None:
    assert RewatchRepository(db_session).collect_inputs() == []

```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_rewatch_repository.py -v`
Expected: FAIL — `ImportError: cannot import name 'RewatchRepository'`.
(If every test *skips* instead, the composed Postgres is down — start it with
`docker compose up postgres` from the repo root and re-run.)

- [ ] **Step 3: Write the implementation**

Replace the entire contents of `backend/app/rewatch/repository.py`:

```python
"""Data-access layer for the rewatch module (DESIGN §5.1, §5.8).

Two reads and one write, no business rules: the FR-RW-02 input assembly, the
whole-list replacement of the projection, and the ordered read the router
serves. Transaction control stays with the caller — only :meth:`commit` commits.

:meth:`collect_inputs` returns :class:`~app.rewatch.algorithm.RewatchInput`
dataclasses rather than ORM rows or raw tuples. The mapping is mechanical, and
the alternative — leaking ``Row`` objects upward — would put the column-name
knowledge in the service instead, which is further from the SQL that produced
it. The algorithm module is dependency-free, so importing its types here costs
nothing.
"""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.films.models import Film
from app.ratings.models import RatingEntry
from app.rewatch.algorithm import DueFilm, RewatchInput
from app.rewatch.models import RewatchSuggestion


class RewatchRepository:
    """SQLAlchemy-backed rewatch data access (one instance per session)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def collect_inputs(self) -> list[RewatchInput]:
        """One aggregate query producing every film's FR-RW-02 payload.

        ``avg`` skips NULL scores on its own, so a film whose every watch went
        unrated reports ``None`` (FR-RAT-11/12) while ``count`` still counts
        those watches. The join is inner: a film with no rating cannot exist
        (FR-LIB-03), and one that somehow did would have no
        ``last_watched_date`` to reason about.
        """
        statement = (
            select(
                Film.id,
                func.avg(RatingEntry.value).label("average_rating"),
                func.count(RatingEntry.id).label("watch_count"),
                func.max(RatingEntry.watch_date).label("last_watched_date"),
                Film.is_favorite,
                Film.delay_days,
            )
            .join(RatingEntry, RatingEntry.film_id == Film.id)
            .group_by(Film.id)
        )
        return [
            RewatchInput(
                film_id=row.id,
                average_rating=row.average_rating,
                watch_count=row.watch_count,
                last_watched_date=row.last_watched_date,
                is_favorite=row.is_favorite,
                delay_days=row.delay_days,
            )
            for row in self._session.execute(statement)
        ]

    def replace_all(self, rows: Sequence[DueFilm], computed_at: datetime) -> None:
        """Swap the whole projection for ``rows``, keeping their order as ``position``.

        Delete-then-insert rather than an upsert: the projection *is* the last
        run's output, so a film absent from ``rows`` must not survive. Both
        statements share the caller's transaction, so a failure mid-run leaves
        the previous projection intact rather than an empty one.
        """
        self._session.execute(delete(RewatchSuggestion))
        self._session.add_all(
            [
                RewatchSuggestion(
                    film_id=row.film_id,
                    days_until_next_rewatch=row.days_until_next_rewatch,
                    position=position,
                    computed_at=computed_at,
                )
                for position, row in enumerate(rows)
            ]
        )

    def list_all(self) -> Sequence[RewatchSuggestion]:
        """The stored due-list in the algorithm's own order (FR-RW-04)."""
        statement = select(RewatchSuggestion).order_by(RewatchSuggestion.position)
        return self._session.scalars(statement).all()

    def commit(self) -> None:
        """Seal the unit of work (the service's call, mirroring ``FilmRepository``)."""
        self._session.commit()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_rewatch_repository.py -v`
Expected: PASS — 7 passed

- [ ] **Step 5: Run the full backend gate**

Run: `cd backend && make typecheck && make lint && make format-check && make test`
Expected: all green.

- [ ] **Step 6: Stop. Do not commit.**

---

## Task 4: The service and its DI wiring

**Files:**
- Modify: `backend/app/rewatch/service.py` (replace the whole stub)
- Create: `backend/app/rewatch/dependencies.py`
- Create: `backend/tests/test_rewatch_service.py`

**Interfaces:**
- Consumes: Task 1's `suggest`/`RewatchInput`/`DueFilm`; Task 3's `RewatchRepository`.
- Produces: `RewatchRepositoryProtocol`; `RewatchService(repository)` with `recompute(today: date) -> int` and `list_suggestions() -> Sequence[RewatchSuggestion]`; `get_rewatch_repository`, `get_rewatch_service` in `dependencies.py`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_rewatch_service.py`. These run offline against a
fake repository — the service holds no SQL, so it needs no database:

```python
"""The rewatch service's orchestration (DESIGN §5.8), against a fake repository (§9)."""

import uuid
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from decimal import Decimal

from app.rewatch.algorithm import BASE_INTERVAL_DAYS, DueFilm, RewatchInput
from app.rewatch.models import RewatchSuggestion
from app.rewatch.service import RewatchService

TODAY = date(2026, 9, 14)


class FakeRepository:
    """Records what the service asked of it (satisfies ``RewatchRepositoryProtocol``)."""

    def __init__(self, inputs: Sequence[RewatchInput]) -> None:
        self._inputs = list(inputs)
        self.stored: list[DueFilm] = []
        self.stored_at: datetime | None = None
        self.commits = 0

    def collect_inputs(self) -> list[RewatchInput]:
        return list(self._inputs)

    def replace_all(self, rows: Sequence[DueFilm], computed_at: datetime) -> None:
        self.stored = list(rows)
        self.stored_at = computed_at

    def list_all(self) -> Sequence[RewatchSuggestion]:
        # Narrowed for pyright strict: ``computed_at`` is a non-optional column,
        # and nothing reads this back before ``replace_all`` has stamped it.
        assert self.stored_at is not None
        return [
            RewatchSuggestion(
                film_id=row.film_id,
                days_until_next_rewatch=row.days_until_next_rewatch,
                position=position,
                computed_at=self.stored_at,
            )
            for position, row in enumerate(self.stored)
        ]

    def commit(self) -> None:
        self.commits += 1


def _input(days_since_watch: int) -> RewatchInput:
    return RewatchInput(
        film_id=uuid.uuid4(),
        average_rating=Decimal("4.0"),
        watch_count=1,
        last_watched_date=TODAY - timedelta(days=days_since_watch),
        is_favorite=False,
        delay_days=0,
    )


def test_recompute_stores_only_the_due_films_and_reports_the_count() -> None:
    repository = FakeRepository([_input(BASE_INTERVAL_DAYS + 5), _input(0)])

    stored_count = RewatchService(repository).recompute(TODAY)

    assert stored_count == 1
    assert [row.days_until_next_rewatch for row in repository.stored] == [-5]


def test_recompute_commits_exactly_once() -> None:
    repository = FakeRepository([_input(BASE_INTERVAL_DAYS)])

    RewatchService(repository).recompute(TODAY)

    assert repository.commits == 1


def test_recompute_stamps_every_row_with_one_timestamp() -> None:
    repository = FakeRepository([_input(BASE_INTERVAL_DAYS)])

    RewatchService(repository).recompute(TODAY)

    assert repository.stored_at is not None


def test_recompute_over_an_empty_library_stores_nothing() -> None:
    repository = FakeRepository([])

    assert RewatchService(repository).recompute(TODAY) == 0
    assert repository.stored == []
    assert repository.commits == 1


def test_list_suggestions_passes_the_stored_order_through_untouched() -> None:
    repository = FakeRepository([_input(BASE_INTERVAL_DAYS + 40), _input(BASE_INTERVAL_DAYS)])
    service = RewatchService(repository)
    service.recompute(TODAY)

    assert [row.days_until_next_rewatch for row in service.list_suggestions()] == [-40, 0]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_rewatch_service.py -v`
Expected: FAIL — `ImportError: cannot import name 'RewatchService'`

- [ ] **Step 3: Write the service**

Replace the entire contents of `backend/app/rewatch/service.py`:

```python
"""Business-logic layer for the rewatch module (DESIGN §5.1, §5.8).

Assembles the FR-RW-02 payload, invokes the pure algorithm, and persists the
ordered result. It depends on the repository through
:class:`RewatchRepositoryProtocol`, so it is unit-testable against a fake (§9),
and it is deliberately unaware of what triggered it — ``scheduler.py`` calls
:meth:`RewatchService.recompute` on a timer, and a test calls it directly.
"""

from collections.abc import Sequence
from datetime import date, datetime
from typing import Protocol

from app.core.db import utc_now
from app.rewatch.algorithm import DueFilm, RewatchInput, suggest
from app.rewatch.models import RewatchSuggestion


class RewatchRepositoryProtocol(Protocol):
    """The data-access interface the service depends on (§5.1)."""

    def collect_inputs(self) -> list[RewatchInput]: ...

    def replace_all(self, rows: Sequence[DueFilm], computed_at: datetime) -> None: ...

    def list_all(self) -> Sequence[RewatchSuggestion]: ...

    def commit(self) -> None: ...


class RewatchService:
    """Runs and serves the daily due-list (DESIGN §5.8)."""

    def __init__(self, repository: RewatchRepositoryProtocol) -> None:
        self._repository = repository

    def recompute(self, today: date) -> int:
        """Run the algorithm over the whole library and store its result.

        ``today`` is a parameter rather than read from the clock in here, so the
        boundary cases (a film due exactly today) are testable without freezing
        time. Returns how many films came back due — the scheduler logs it.
        """
        due = suggest(self._repository.collect_inputs(), today)
        self._repository.replace_all(due, utc_now())
        self._repository.commit()
        return len(due)

    def list_suggestions(self) -> Sequence[RewatchSuggestion]:
        """The stored due-list. Never recomputes — that is the daily job's alone (§5.8)."""
        return self._repository.list_all()
```

- [ ] **Step 4: Write the DI wiring**

Create `backend/app/rewatch/dependencies.py`:

```python
"""FastAPI dependency providers for the rewatch module (DESIGN §5.1).

Wires the layer chain for injection into the route: request-scoped session →
:class:`RewatchRepository` → :class:`RewatchService`. The router only ever
depends on the service.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.rewatch.repository import RewatchRepository
from app.rewatch.service import RewatchService


def get_rewatch_repository(session: Annotated[Session, Depends(get_session)]) -> RewatchRepository:
    """Repository bound to the request's session."""
    return RewatchRepository(session)


def get_rewatch_service(
    repository: Annotated[RewatchRepository, Depends(get_rewatch_repository)],
) -> RewatchService:
    """Service over the request's repository (the seam tests override)."""
    return RewatchService(repository)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_rewatch_service.py -v`
Expected: PASS — 5 passed

- [ ] **Step 6: Run the full backend gate**

Run: `cd backend && make typecheck && make lint && make format-check && make test`
Expected: all green.

- [ ] **Step 7: Stop. Do not commit.**

---

## Task 5: The endpoint

**Files:**
- Modify: `backend/app/rewatch/schemas.py` (replace the whole stub)
- Modify: `backend/app/rewatch/router.py` (replace the whole stub)
- Modify: `backend/app/main.py` — `build_api_router` docstring, app `version`, app `description`
- Modify: `backend/tests/test_openapi_contract.py:32-45` — add the route to `_M1_ROUTES`
- Create: `backend/tests/test_rewatch_api.py`

**Interfaces:**
- Consumes: Task 4's `get_rewatch_service`, `RewatchService`.
- Produces: `RewatchSuggestionRead` (fields `film_id: UUID`, `days_until_next_rewatch: int`); the route `GET /api/v1/rewatch-suggestions` returning `list[RewatchSuggestionRead]`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_rewatch_api.py`:

```python
"""``GET /rewatch-suggestions`` end to end (DESIGN §5.3, FR-RW-03/04/06).

Offline: the service dependency is overridden with a stub, so the route's
serialisation and ordering are tested without a database.
"""

import uuid
from collections.abc import Sequence

from fastapi.testclient import TestClient

from app.core.db import utc_now
from app.main import create_app
from app.rewatch.dependencies import get_rewatch_service
from app.rewatch.models import RewatchSuggestion


def _client(rows: Sequence[RewatchSuggestion]) -> TestClient:
    app = create_app()

    class StubService:
        def list_suggestions(self) -> Sequence[RewatchSuggestion]:
            return rows

    app.dependency_overrides[get_rewatch_service] = StubService
    return TestClient(app)


def _row(days: int, position: int) -> RewatchSuggestion:
    return RewatchSuggestion(
        film_id=uuid.uuid4(),
        days_until_next_rewatch=days,
        position=position,
        computed_at=utc_now(),
    )


def test_an_empty_projection_serves_an_empty_list() -> None:
    # FR-RW-06: the empty state is the view's job, not an error here.
    response = _client([]).get("/api/v1/rewatch-suggestions")

    assert response.status_code == 200
    assert response.json() == []


def test_the_response_carries_only_the_two_contract_fields() -> None:
    row = _row(-12, 0)

    response = _client([row]).get("/api/v1/rewatch-suggestions")

    assert response.json() == [
        {"film_id": str(row.film_id), "days_until_next_rewatch": -12}
    ]


def test_the_stored_order_reaches_the_wire_unchanged() -> None:
    # FR-RW-04: the API re-sorts nothing; it serves what the run stored.
    rows = [_row(-40, 0), _row(-1, 1), _row(0, 2)]

    payload = _client(rows).get("/api/v1/rewatch-suggestions").json()

    assert [item["days_until_next_rewatch"] for item in payload] == [-40, -1, 0]
    assert [item["film_id"] for item in payload] == [str(row.film_id) for row in rows]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_rewatch_api.py -v`
Expected: FAIL — 404, the route does not exist yet.

- [ ] **Step 3: Write the schema**

Replace the entire contents of `backend/app/rewatch/schemas.py`:

```python
"""Pydantic response schemas for the rewatch module (DESIGN §5.3, §5.8).

Read-only: the projection is written by the daily job, never by a request, so
there is no request schema here.
"""

from uuid import UUID

from pydantic import ConfigDict

from app.core.schemas import StrictSchema


class RewatchSuggestionRead(StrictSchema):
    """One due film as served by ``GET /rewatch-suggestions`` (FR-RW-03).

    Deliberately carries no film metadata: the client already holds the whole
    library from ``GET /films`` and joins on ``film_id`` locally (§6.3).
    """

    # Merged into the strict base config: allows building the schema straight
    # from the ORM row while the model stays strict and closed.
    model_config = ConfigDict(from_attributes=True)

    film_id: UUID
    # ``0`` is due today; a negative value is overdue by that many days. Never
    # positive — not-yet-due films are omitted from the list entirely.
    days_until_next_rewatch: int
```

- [ ] **Step 4: Write the router**

Replace the entire contents of `backend/app/rewatch/router.py`:

```python
"""Presentation layer for the rewatch module (DESIGN §5.1, §5.8).

The single route under ``/api/v1/rewatch-suggestions`` (mounted by the app
factory). It serves the **stored** result of the daily job and never runs the
algorithm — per-request computation is exactly what the daily cadence exists to
avoid (§5.8). There is no write route and no refresh route: the projection is
the scheduler's alone.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.rewatch.dependencies import get_rewatch_service
from app.rewatch.schemas import RewatchSuggestionRead
from app.rewatch.service import RewatchService

router = APIRouter()


@router.get(
    "",
    summary="List rewatch suggestions",
    description=(
        "The latest daily-computed due-list (FR-RW-03/04/05): the films that "
        "are due or overdue for a rewatch, **most overdue first**. Not-yet-due "
        "films are omitted, so `days_until_next_rewatch` is always `<= 0` — "
        "`0` means due today. The order is the algorithm's own and must not be "
        "re-sorted by the client (FR-RW-04). Because the job runs once a day, "
        "a film that becomes newly due purely by the passage of time appears "
        "at the next run (an accepted ~24h lag). An empty list is a normal "
        "answer, not an error (FR-RW-06)."
    ),
)
def list_rewatch_suggestions(
    service: Annotated[RewatchService, Depends(get_rewatch_service)],
) -> list[RewatchSuggestionRead]:
    return [RewatchSuggestionRead.model_validate(row) for row in service.list_suggestions()]
```

There is no `responses=error_responses(...)`: the route takes no path
parameter, no query parameter and no body, so none of the documented error
codes can arise from it.

- [ ] **Step 5: Update `main.py`**

Three edits in `backend/app/main.py`:

1. In `build_api_router`'s docstring, replace the sentence beginning "Films,
   ratings, tags, and genres carry the full M1 core-domain surface" with:

```
    Films, ratings, tags, and genres carry the core-domain surface, and rewatch
    serves the M4 daily due-list (§5.8) — the §5.1 wiring holds throughout: a
    router never imports a repository.
```

2. Change `version="0.2.0"` to `version="0.3.0"` and replace the comment above
   it with:

```python
        # App version (SemVer 2.0.0, policy in the root README). The /api/vN
        # contract is SemVer's "public API": breaking it bumps MAJOR and the
        # URL version together. M4 adds the rewatch-suggestions route without
        # touching any existing one, so this is a MINOR bump.
```

3. In the app `description`, replace the final sentence
   `"Listing/search, merge, and rewatch suggestions are later milestones."`
   with `"Listing/search and merge are later milestones."`

- [ ] **Step 6: Update the OpenAPI contract test**

In `backend/tests/test_openapi_contract.py`, add to the `_M1_ROUTES` set
(after the `genres` entry), keeping the set's existing comment style:

```python
    # M4's rewatch engine (§5.8) — the stored daily due-list.
    ("GET", "/api/v1/rewatch-suggestions"),
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_rewatch_api.py tests/test_openapi_contract.py -v`
Expected: PASS

- [ ] **Step 8: Run the full backend gate**

Run: `cd backend && make typecheck && make lint && make format-check && make test`
Expected: all green.

- [ ] **Step 9: Stop. Do not commit.**

---

## Task 6: The daily scheduler

**Files:**
- Modify: `backend/app/core/db.py` — add `session_scope`, refactor `get_session` onto it
- Modify: `backend/app/core/config.py` — add `rewatch_recompute_interval_seconds`
- Modify: `backend/.env.example` — document the new variable
- Create: `backend/app/rewatch/scheduler.py`
- Modify: `backend/app/main.py` — pass `lifespan=` to `FastAPI(...)`
- Create: `backend/tests/test_rewatch_scheduler.py`

**Interfaces:**
- Consumes: Task 3's `RewatchRepository`, Task 4's `RewatchService`.
- Produces: `app.core.db.session_scope() -> AbstractContextManager[Session]`; `app.rewatch.scheduler.recompute_once() -> None`; `app.rewatch.scheduler.lifespan(app: FastAPI)`; `Settings.rewatch_recompute_interval_seconds: int`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_rewatch_scheduler.py`:

```python
"""The daily recompute trigger (DESIGN §5.8, §8.1) — offline.

What matters here is the *wiring*, not the arithmetic: that the app starts and
stops the task cleanly, that a failing run cannot take the loop or the app
down, and that the interval is configurable.
"""

import time

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app
from app.rewatch import scheduler


def test_a_failing_run_is_swallowed_and_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # A run that raises must leave the previous projection in place and let the
    # loop live — a dead scheduler would silently freeze the due-list forever.
    def explode() -> None:
        raise RuntimeError("database is down")

    monkeypatch.setattr(scheduler, "_recompute", explode)

    scheduler.recompute_once()

    assert "rewatch recompute failed" in caplog.text


def test_the_app_starts_the_task_and_cancels_it_on_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runs: list[int] = []
    monkeypatch.setattr(scheduler, "recompute_once", lambda: runs.append(1))

    with TestClient(create_app()) as client:
        assert client.get("/api/v1/health").status_code == 200
        # ``create_task`` only schedules; without waiting, shutdown can cancel
        # the task before it reaches its first run and the assertion below
        # would flake. Poll rather than sleep a fixed time, so the common case
        # costs a few milliseconds.
        deadline = time.monotonic() + 2
        while not runs and time.monotonic() < deadline:
            time.sleep(0.01)

    # One run at startup (the loop then sleeps until the next interval).
    assert runs == [1]


def test_the_interval_is_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REWATCH_RECOMPUTE_INTERVAL_SECONDS", "60")
    get_settings.cache_clear()
    try:
        assert get_settings().rewatch_recompute_interval_seconds == 60
    finally:
        get_settings.cache_clear()


def test_the_interval_defaults_to_one_day() -> None:
    assert get_settings().rewatch_recompute_interval_seconds == 86_400
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_rewatch_scheduler.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.rewatch.scheduler'`

- [ ] **Step 3: Add `session_scope` to `core/db.py`**

The scheduler runs outside the request cycle, so it cannot use the
`get_session` FastAPI dependency. Add the context manager and rebuild
`get_session` on top of it so there is still one place that opens and closes a
session.

Add `from contextlib import contextmanager` to the imports, then replace the
existing `get_session` function with:

```python
@contextmanager
def session_scope() -> Iterator[Session]:
    """A session outside the request cycle (the rewatch scheduler, §5.8).

    Same lifecycle as :func:`get_session`, usable with ``with``. Committing is
    the caller's business, as everywhere else.
    """
    session = _session_factory()()
    try:
        yield session
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI request-scoped session dependency (DESIGN §5.1 data-access).

    Yields a session for the lifetime of one request and always closes it.
    Routers never use this directly — the repositories depend on it, keeping
    business logic free of session lifecycle concerns.
    """
    with session_scope() as session:
        yield session
```

- [ ] **Step 4: Add the setting**

In `backend/app/core/config.py`, add to `Settings` after the `port` field:

```python
    # How often the rewatch due-list is recomputed (DESIGN §5.8). The contract
    # is "once daily", so this is a day; it exists as a setting because tests
    # and a manual check need a shorter cycle.
    rewatch_recompute_interval_seconds: int = 86_400
```

In `backend/.env.example`, add beneath the existing entries, matching the
file's comment style:

```
# How often the rewatch due-list is recomputed, in seconds (DESIGN §5.8).
# Defaults to one day; shorten it only for local experimentation.
REWATCH_RECOMPUTE_INTERVAL_SECONDS=86400
```

- [ ] **Step 5: Write the scheduler**

Create `backend/app/rewatch/scheduler.py`:

```python
"""The once-daily rewatch trigger (DESIGN §5.8, §8.1, FR-RW-05).

An in-process asyncio task owned by the app's lifespan, rather than a cron
container beside it: the deployment target is a single laptop running one
container (§1.3), where a scheduler that lives and dies with the app is the
whole requirement — and every start recomputes, so a restart costs nothing.
(OPEN_DECISIONS_V1 "M4 — Scheduler mechanism".)

The cadence is "one interval since the last run", not a wall-clock time of day.
The §5.8 contract only asks for once-daily, and an interval sleep needs no
timezone reasoning.

This module is infrastructure. The algorithm and the service stay unaware of it.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from datetime import date

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.db import session_scope
from app.rewatch.repository import RewatchRepository
from app.rewatch.service import RewatchService

_logger = logging.getLogger(__name__)


def _recompute() -> None:
    """One run against its own session — the unit the loop repeats."""
    with session_scope() as session:
        count = RewatchService(RewatchRepository(session)).recompute(date.today())
    _logger.info("rewatch recompute stored %d due films", count)


def recompute_once() -> None:
    """Run the recompute, swallowing and logging any failure.

    A raising run must not kill the loop: a dead scheduler would freeze the
    due-list at whatever the last successful run produced, silently and
    forever. The previous projection survives untouched (``replace_all`` and
    the insert share one transaction), which is also what FR-RW-07 wants — the
    client keeps showing the last good list.
    """
    try:
        _recompute()
    except Exception:
        _logger.exception("rewatch recompute failed; keeping the previous projection")


async def _run_forever(interval_seconds: int) -> None:
    """Recompute at startup, then once per interval."""
    while True:
        # The recompute is blocking DB work; off the event loop it goes, so a
        # run never stalls the requests the same process is serving.
        await asyncio.to_thread(recompute_once)
        await asyncio.sleep(interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Start the daily task with the app and cancel it on shutdown."""
    task = asyncio.create_task(_run_forever(get_settings().rewatch_recompute_interval_seconds))
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
```

Note the indirection: `recompute_once` calls the module-level `_recompute`, and
`_run_forever` calls the module-level `recompute_once`. Both tests monkeypatch
one of those names, which only works because each call goes through the module
attribute rather than a captured local.

- [ ] **Step 6: Wire the lifespan into the app factory**

In `backend/app/main.py`, add `from app.rewatch.scheduler import lifespan` to
the imports and pass it to the constructor:

```python
    app = FastAPI(
        title="Film Rewatch API",
        # The once-daily rewatch recompute runs as a task owned by this
        # lifespan (§5.8) — it starts with the app and is cancelled with it.
        lifespan=lifespan,
        version="0.3.0",
        ...
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_rewatch_scheduler.py -v`
Expected: PASS — 4 passed

- [ ] **Step 8: Run the full backend gate**

Run: `cd backend && make typecheck && make lint && make format-check && make test`
Expected: all green. Every other test builds the app through `create_app()`
without entering its lifespan (`TestClient` used as a plain object, not a
context manager), so no other test starts the scheduler.

- [ ] **Step 9: Verify it runs for real**

Run, from the repo root, with the composed Postgres up:
```bash
cd backend && REWATCH_RECOMPUTE_INTERVAL_SECONDS=30 uv run uvicorn app.main:app
```
Expected: an `INFO` line `rewatch recompute stored N due films` at startup, and
`curl localhost:8000/api/v1/rewatch-suggestions` returns a JSON array. Stop the
server afterwards.

- [ ] **Step 10: Stop. Do not commit.**

---

## Task 7: Shared rating-star helpers

**Files:**
- Create: `frontend/src/app/shared/rating-stars.ts`
- Create: `frontend/src/app/shared/rating-stars.spec.ts`
- Modify: `frontend/src/app/views/library/library.ts` — delete the local `ratingStars`, import the shared one, use `ratingLabelFor`

**Interfaces:**
- Consumes: nothing.
- Produces: `ratingStarsFor(rating: number | null): readonly string[] | null`; `ratingLabelFor(rating: number | null): string`.

The Rewatch card renders the same five-star row as the Library row. Extracting
the two pure functions removes the duplication before it is written.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/app/shared/rating-stars.spec.ts`:

```ts
/** The one star-rendering rule both the library list and the rewatch grid use (FR-RAT-13). */
import { ratingLabelFor, ratingStarsFor } from './rating-stars';

describe('ratingStarsFor', () => {
  it('fills whole stars up to the rating', () => {
    expect(ratingStarsFor(3)).toEqual(['star', 'star', 'star', 'star_border', 'star_border']);
  });

  it('renders a half star for a half-point rating', () => {
    expect(ratingStarsFor(3.5)).toEqual(['star', 'star', 'star', 'star_half', 'star_border']);
  });

  it('rounds to the nearest half star', () => {
    expect(ratingStarsFor(3.7)).toEqual(['star', 'star', 'star', 'star_half', 'star_border']);
  });

  it('returns null for an unrated film', () => {
    // Five empty stars would read as "rated zero", the opposite of "not rated" (FR-RAT-11/13).
    expect(ratingStarsFor(null)).toBeNull();
  });
});

describe('ratingLabelFor', () => {
  it('states the average out of five', () => {
    expect(ratingLabelFor(4.25)).toBe('Average rating: 4.3 out of 5');
  });

  it('says so when nothing was rated', () => {
    expect(ratingLabelFor(null)).toBe('Not rated');
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npm test -- rating-stars`
Expected: FAIL — cannot resolve `./rating-stars`

- [ ] **Step 3: Write the implementation**

Create `frontend/src/app/shared/rating-stars.ts`:

```ts
/**
 * The app's one star-rendering rule (FR-RAT-09/11/13, DESIGN §6.5 shared/).
 *
 * Extracted from the library view when the rewatch grid needed the same five
 * icons: two views rounding half-stars independently would eventually disagree.
 * These are functions, not a component — the markup they feed is a five-item
 * `@for`, which is not yet worth a component of its own.
 */

/** Material icon names for the five positions, rounded to the nearest half star; `null` for an unrated film. */
export function ratingStarsFor(rating: number | null): readonly string[] | null {
  if (rating === null) return null;
  const rounded = Math.round(rating * 2) / 2;
  return Array.from({ length: 5 }, (_, index) => {
    const position = index + 1;
    if (rounded >= position) return 'star';
    if (position - rounded === 0.5) return 'star_half';
    return 'star_border';
  });
}

/** The accessible label for the star row — the icons themselves are `aria-hidden`. */
export function ratingLabelFor(rating: number | null): string {
  return rating === null ? 'Not rated' : `Average rating: ${rating.toFixed(1)} out of 5`;
}
```

- [ ] **Step 4: Point the library view at the shared helpers**

In `frontend/src/app/views/library/library.ts`:
- Delete the local `ratingStars` function and its doc comment entirely.
- Add `import { ratingLabelFor, ratingStarsFor } from '../../shared/rating-stars';`
- In the `rows` computed, replace `ratingStars: ratingStars(film.averageRating),` with `ratingStars: ratingStarsFor(film.averageRating),`
- Replace the whole `ratingLabel:` line (currently a ternary) with `ratingLabel: ratingLabelFor(film.averageRating),`

Leave `FilmRowVm.ratingStars`'s doc comment in place — it documents the field,
not the function.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd frontend && npm test`
Expected: PASS — the new spec plus the existing library spec, unchanged.

- [ ] **Step 6: Run the full frontend gate**

Run: `cd frontend && npm run build && npm test && npm run lint`
Expected: all green.

- [ ] **Step 7: Stop. Do not commit.**

---

## Task 8: The rewatch domain layer

**Files:**
- Create: `frontend/src/app/domain/rewatch/api.ts`
- Create: `frontend/src/app/domain/rewatch/model.ts`
- Create: `frontend/src/app/domain/rewatch/mapper.ts`
- Create: `frontend/src/app/domain/rewatch/facade.ts`
- Create: `frontend/src/app/domain/rewatch/README.md`
- Create: `frontend/src/app/domain/rewatch/rewatch-mapper.spec.ts`
- Create: `frontend/src/app/domain/rewatch/rewatch-facade.spec.ts`

**Interfaces:**
- Consumes: Task 7's `ratingStarsFor`/`ratingLabelFor`; `FilmFacade.films`/`isLoading`/`error`; `Film` from `domain/film/model`.
- Produces: `RewatchSuggestionDto { film_id, days_until_next_rewatch }`; `RewatchApi.list`; `RewatchSuggestion { filmId, daysUntilNextRewatch }`; `RewatchCardVm { id, title, year, posterImage, ratingStars, ratingLabel, isFavorite, dueLabel }`; `dueLabelFor(days: number): string`; `toRewatchSuggestion(dto)`; `toRewatchCardVm(film, suggestion)`; `RewatchFacade` with `cards`, `isLoading`, `error`, `removeFilm(filmId)`, `reload()`.

- [ ] **Step 1: Write the failing mapper test**

Create `frontend/src/app/domain/rewatch/rewatch-mapper.spec.ts`:

```ts
/** DTO → domain mapping and the §7.1 "Rewatch status" wording. */
import type { Film } from '../film/model';
import { dueLabelFor, toRewatchCardVm, toRewatchSuggestion } from './mapper';

const HEAT: Film = {
  id: 'f1',
  primaryTitle: 'Heat',
  releaseYear: 1995,
  director: 'Michael Mann',
  runtimeMinutes: 170,
  genres: ['Crime'],
  tags: ['heist'],
  posterImage: null,
  averageRating: 4,
  isFavorite: true,
  titles: [{ value: 'Heat', isPrimary: true, isOriginal: true }],
};

describe('toRewatchSuggestion', () => {
  it('maps the snake_case wire shape to the domain model', () => {
    expect(toRewatchSuggestion({ film_id: 'f1', days_until_next_rewatch: -3 })).toEqual({
      filmId: 'f1',
      daysUntilNextRewatch: -3,
    });
  });
});

describe('dueLabelFor', () => {
  it('reads "Due now" at zero', () => {
    expect(dueLabelFor(0)).toBe('Due now');
  });

  it('counts the days a film is overdue', () => {
    expect(dueLabelFor(-12)).toBe('Overdue by 12 days');
  });

  it('says "day" for exactly one', () => {
    expect(dueLabelFor(-1)).toBe('Overdue by 1 day');
  });
});

describe('toRewatchCardVm', () => {
  it('shapes the §7.1 card from the film and its suggestion', () => {
    const card = toRewatchCardVm(HEAT, { filmId: 'f1', daysUntilNextRewatch: -5 });

    expect(card).toEqual({
      id: 'f1',
      title: 'Heat',
      year: 1995,
      posterImage: null,
      ratingStars: ['star', 'star', 'star', 'star', 'star_border'],
      ratingLabel: 'Average rating: 4.0 out of 5',
      isFavorite: true,
      dueLabel: 'Overdue by 5 days',
    });
  });

  it('carries the unrated placeholder through', () => {
    const card = toRewatchCardVm({ ...HEAT, averageRating: null }, { filmId: 'f1', daysUntilNextRewatch: 0 });

    expect(card.ratingStars).toBeNull();
    expect(card.ratingLabel).toBe('Not rated');
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && npm test -- rewatch-mapper`
Expected: FAIL — cannot resolve `./mapper`

- [ ] **Step 3: Write `api.ts`, `model.ts`, `mapper.ts`**

Create `frontend/src/app/domain/rewatch/api.ts`:

```ts
/**
 * Rewatch data access (DESIGN §6.1, §6.3) — the only place that speaks the wire shape.
 *
 * Read-only: the due-list is computed and stored by the backend's daily job
 * (§5.8), so there is no write here. The client's one local change to it —
 * removing a film the user just watched — is `RewatchFacade.removeFilm`,
 * which edits the cached value rather than calling the API.
 */
import { httpResource } from '@angular/common/http';
import { Injectable } from '@angular/core';

import { environment } from '../../../environments/environment';

/** One entry of the daily due-list (mirrors `RewatchSuggestionRead`). */
export interface RewatchSuggestionDto {
  readonly film_id: string;
  /** Always `<= 0`: `0` is due today, negative is overdue by that many days. */
  readonly days_until_next_rewatch: number;
}

@Injectable({ providedIn: 'root' })
export class RewatchApi {
  /**
   * `GET /rewatch-suggestions` — the stored result of the last daily run.
   *
   * An `httpResource` for the same reason `FilmApi.list` is one: it exposes
   * loading and error as signals, which is the loading/empty/error triple
   * §7.1 has to render. Its `value` is writable, which is what makes the
   * §6.3 optimistic removal a local update rather than a refetch.
   */
  readonly list = httpResource<readonly RewatchSuggestionDto[]>(
    () => `${environment.apiBaseUrl}/rewatch-suggestions`,
    { defaultValue: [] },
  );
}
```

Create `frontend/src/app/domain/rewatch/model.ts`:

```ts
/** The rewatch domain model and the §7.1 card ViewModel (DESIGN §6.1). */

/** One entry of the due-list, as the algorithm ordered it (FR-RW-03). */
export interface RewatchSuggestion {
  readonly filmId: string;
  /** `0` is due today; negative is overdue by that many days. Never positive. */
  readonly daysUntilNextRewatch: number;
}

/**
 * One card of the §7.1 grid — a suggestion joined to its film. Display-ready:
 * the view prints these fields and computes nothing.
 */
export interface RewatchCardVm {
  readonly id: string;
  readonly title: string;
  readonly year: number;
  readonly posterImage: string | null;
  /** Five Material star icon names, or `null` for an unrated film (FR-RAT-13). */
  readonly ratingStars: readonly string[] | null;
  readonly ratingLabel: string;
  readonly isFavorite: boolean;
  /** "Due now" or "Overdue by N days" (§7.1 Rewatch status). */
  readonly dueLabel: string;
}
```

Create `frontend/src/app/domain/rewatch/mapper.ts`:

```ts
/** DTO → domain → ViewModel mapping for rewatch suggestions (DESIGN §6.1). */
import { ratingLabelFor, ratingStarsFor } from '../../shared/rating-stars';
import type { Film } from '../film/model';
import type { RewatchSuggestionDto } from './api';
import type { RewatchCardVm, RewatchSuggestion } from './model';

export function toRewatchSuggestion(dto: RewatchSuggestionDto): RewatchSuggestion {
  return { filmId: dto.film_id, daysUntilNextRewatch: dto.days_until_next_rewatch };
}

/** The §7.1 "Rewatch status" wording. Only `<= 0` can reach here (FR-RW-03). */
export function dueLabelFor(daysUntilNextRewatch: number): string {
  if (daysUntilNextRewatch >= 0) return 'Due now';
  const days = -daysUntilNextRewatch;
  return `Overdue by ${days} day${days === 1 ? '' : 's'}`;
}

/** Joins a suggestion to its film to produce one card (§6.3). */
export function toRewatchCardVm(film: Film, suggestion: RewatchSuggestion): RewatchCardVm {
  return {
    id: film.id,
    title: film.primaryTitle,
    year: film.releaseYear,
    posterImage: film.posterImage,
    ratingStars: ratingStarsFor(film.averageRating),
    ratingLabel: ratingLabelFor(film.averageRating),
    isFavorite: film.isFavorite,
    dueLabel: dueLabelFor(suggestion.daysUntilNextRewatch),
  };
}
```

- [ ] **Step 4: Run the mapper test to verify it passes**

Run: `cd frontend && npm test -- rewatch-mapper`
Expected: PASS

- [ ] **Step 5: Write the failing facade test**

Create `frontend/src/app/domain/rewatch/rewatch-facade.spec.ts`:

```ts
/** The join, the order guarantee, and the §6.3 optimistic removal. */
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';

import { FilmFacade } from '../film/facade';
import type { Film } from '../film/model';
import type { RewatchSuggestionDto } from './api';
import { RewatchApi } from './api';
import { RewatchFacade } from './facade';

function film(id: string, title: string, rating: number | null = 4): Film {
  return {
    id,
    primaryTitle: title,
    releaseYear: 1995,
    director: 'Michael Mann',
    runtimeMinutes: 170,
    genres: [],
    tags: [],
    posterImage: null,
    averageRating: rating,
    isFavorite: false,
    titles: [{ value: title, isPrimary: true, isOriginal: true }],
  };
}

function configure(films: readonly Film[], suggestions: readonly RewatchSuggestionDto[]) {
  const value = signal<readonly RewatchSuggestionDto[]>(suggestions);
  const apiStub = {
    list: {
      value,
      isLoading: signal(false),
      error: signal(undefined),
      reload: (): void => undefined,
    },
  };
  TestBed.configureTestingModule({
    providers: [
      { provide: RewatchApi, useValue: apiStub },
      {
        provide: FilmFacade,
        useValue: { films: signal(films), isLoading: signal(false), error: signal(undefined) },
      },
    ],
  });
  return { facade: TestBed.inject(RewatchFacade), value };
}

describe('RewatchFacade', () => {
  it('joins each suggestion to its film', () => {
    const { facade } = configure([film('f1', 'Heat')], [{ film_id: 'f1', days_until_next_rewatch: -2 }]);

    expect(facade.cards().map((card) => [card.title, card.dueLabel])).toEqual([['Heat', 'Overdue by 2 days']]);
  });

  it('keeps the suggestion order even when the library is ordered differently', () => {
    // FR-RW-04: the client never re-sorts the algorithm's output.
    const { facade } = configure(
      [film('f1', 'Heat'), film('f2', 'Se7en')],
      [
        { film_id: 'f2', days_until_next_rewatch: -40 },
        { film_id: 'f1', days_until_next_rewatch: 0 },
      ],
    );

    expect(facade.cards().map((card) => card.title)).toEqual(['Se7en', 'Heat']);
  });

  it('skips a suggestion whose film the library does not hold', () => {
    const { facade } = configure(
      [film('f1', 'Heat')],
      [
        { film_id: 'ghost', days_until_next_rewatch: -9 },
        { film_id: 'f1', days_until_next_rewatch: 0 },
      ],
    );

    expect(facade.cards().map((card) => card.title)).toEqual(['Heat']);
  });

  it('removes exactly one film from the due-list on request', () => {
    const { facade } = configure(
      [film('f1', 'Heat'), film('f2', 'Se7en')],
      [
        { film_id: 'f1', days_until_next_rewatch: -1 },
        { film_id: 'f2', days_until_next_rewatch: -2 },
      ],
    );

    facade.removeFilm('f1');

    expect(facade.cards().map((card) => card.title)).toEqual(['Se7en']);
  });

  it('ignores a removal for a film that is not due', () => {
    const { facade } = configure([film('f1', 'Heat')], [{ film_id: 'f1', days_until_next_rewatch: 0 }]);

    facade.removeFilm('f2');

    expect(facade.cards()).toHaveLength(1);
  });

  it('has no cards for an empty due-list', () => {
    const { facade } = configure([film('f1', 'Heat')], []);

    expect(facade.cards()).toEqual([]);
  });
});
```

- [ ] **Step 6: Run it to verify it fails**

Run: `cd frontend && npm test -- rewatch-facade`
Expected: FAIL — cannot resolve `./facade`

- [ ] **Step 7: Write the facade**

Create `frontend/src/app/domain/rewatch/facade.ts`:

```ts
/**
 * The rewatch business-logic facade (DESIGN §6.1, §6.3) — the single API the view calls.
 *
 * The due-list arrives as bare `film_id`s (§5.8); this is where each one is
 * joined to the cached film metadata to make a card. The view therefore holds
 * no lookup logic and no ordering logic of its own.
 */
import { Injectable, computed, inject } from '@angular/core';

import { FilmFacade } from '../film/facade';
import { RewatchApi } from './api';
import { toRewatchCardVm, toRewatchSuggestion } from './mapper';
import type { RewatchCardVm } from './model';

@Injectable({ providedIn: 'root' })
export class RewatchFacade {
  private readonly api = inject(RewatchApi);
  private readonly films = inject(FilmFacade);

  /**
   * The §7.1 grid, in the algorithm's order (FR-RW-04) — this never sorts.
   *
   * A suggestion whose film the library does not hold is dropped rather than
   * rendered as a blank card: the two lists are fetched separately, so a film
   * deleted since the last daily run can still appear in the due-list. It
   * disappears for good at the next run.
   */
  readonly cards = computed<readonly RewatchCardVm[]>(() => {
    const byId = new Map(this.films.films().map((film) => [film.id, film]));
    return this.api.list.value().flatMap((dto) => {
      const suggestion = toRewatchSuggestion(dto);
      const film = byId.get(suggestion.filmId);
      return film === undefined ? [] : [toRewatchCardVm(film, suggestion)];
    });
  });

  /** Either request being in flight counts — a card needs both to have landed. */
  readonly isLoading = computed(() => this.api.list.isLoading() || this.films.isLoading());
  readonly error = computed(() => this.api.list.error() ?? this.films.error());

  /**
   * Drop a film from the displayed due-list (§6.3 optimistic removal).
   *
   * Called when a watch is logged for it anywhere in the app: a film watched
   * today will not be due again for a while, and waiting for tomorrow's run to
   * say so would leave it sitting in the grid. Local only — the daily job
   * stays authoritative and restores the film at the next fetch if it really
   * is still due, which makes this self-correcting rather than a guess.
   */
  removeFilm(filmId: string): void {
    this.api.list.value.update((suggestions) =>
      suggestions.filter((suggestion) => suggestion.film_id !== filmId),
    );
  }

  /** Re-fetch the due-list (from an error state). */
  reload(): void {
    this.api.list.reload();
  }
}
```

- [ ] **Step 8: Write the module README**

Create `frontend/src/app/domain/rewatch/README.md`:

```markdown
# `domain/rewatch/` — the due-list

Data access and business logic for the rewatch suggestions (DESIGN §6.3).

The algorithm runs on the backend (§5.8); this layer only consumes its result.
The wire shape is bare `film_id` + `days_until_next_rewatch`, so `facade.ts`
joins each entry to the cached film metadata from `domain/film/` to produce the
cards `views/rewatch/` renders — in the algorithm's order, never re-sorted
(FR-RW-04).

`removeFilm` is the one client-side rule here: a film the user has just watched
leaves the list immediately rather than waiting for tomorrow's run.
```

- [ ] **Step 9: Run the tests to verify they pass**

Run: `cd frontend && npm test -- rewatch`
Expected: PASS — the mapper spec and the facade spec.

- [ ] **Step 10: Run the full frontend gate**

Run: `cd frontend && npm run build && npm test && npm run lint`
Expected: all green.

- [ ] **Step 11: Stop. Do not commit.**

---

## Task 9: Optimistic removal on watch

**Files:**
- Modify: `frontend/src/app/domain/rating/facade.ts`
- Modify: `frontend/src/app/domain/rating/rating-facade.spec.ts`

**Interfaces:**
- Consumes: Task 8's `RewatchFacade.removeFilm`.
- Produces: no new exports — `RatingFacade.add` gains a side effect.

- [ ] **Step 1: Write the failing test**

Read `frontend/src/app/domain/rating/rating-facade.spec.ts` first and follow
its existing stub style. Append a test to the `add` describe block (adapt the
stub construction to match what is already there):

```ts
  it('removes the film from the due-list once its watch is logged', async () => {
    // §6.3: a freshly watched film leaves the rewatch grid at once, from
    // wherever the watch was logged, without waiting for tomorrow's run.
    const removeFilm = vi.fn();
    // ... build the facade with { provide: RewatchFacade, useValue: { removeFilm } }
    // alongside the existing RatingApi / FilmFacade stubs.

    await firstValueFrom(facade.add('f1', draft));

    expect(removeFilm).toHaveBeenCalledWith('f1');
  });
```

Add a matching negative case in the same style: when `api.add` errors, the
`tap` never runs, so `removeFilm` must not be called.

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && npm test -- rating-facade`
Expected: FAIL — `removeFilm` was not called.

- [ ] **Step 3: Write the implementation**

In `frontend/src/app/domain/rating/facade.ts`:

- Add `import { RewatchFacade } from '../rewatch/facade';`
- Add the field `private readonly rewatch = inject(RewatchFacade);` beneath the existing `films` field.
- Extend `add`'s `tap` to do both things:

```ts
  /** `POST /films/{id}/ratings`; on success, prepends the new entry and recomputes the average locally. */
  add(filmId: string, draft: RatingDraft): Observable<void> {
    return this.api.add(filmId, toRatingCreateDto(draft)).pipe(
      tap((entry) => {
        this.films.applyRatingAdded(filmId, entry);
        // §6.3 optimistic removal: a film watched today will not be due again
        // for a while, so it leaves the rewatch grid now rather than at the
        // next daily run. Self-correcting — tomorrow's fetch restores it if
        // the algorithm disagrees.
        this.rewatch.removeFilm(filmId);
      }),
      map(() => undefined),
    );
  }
```

- Extend the class docstring's second paragraph to mention that a watch also
  updates the due-list, citing §6.3.

`RewatchFacade` injects `FilmFacade`, and `RatingFacade` injects both — no
cycle, and both are business-logic-layer facades, so this is a sideways call
§6.1 permits.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npm test -- rating-facade`
Expected: PASS

- [ ] **Step 5: Run the full frontend gate**

Run: `cd frontend && npm run build && npm test && npm run lint`
Expected: all green — the film-detail view's rating flow goes through this
facade and must still pass its own spec.

- [ ] **Step 6: Stop. Do not commit.**

---

## Task 10: The Rewatch view

**Files:**
- Create: `frontend/src/app/views/rewatch/rewatch.ts`
- Create: `frontend/src/app/views/rewatch/rewatch.html`
- Create: `frontend/src/app/views/rewatch/rewatch.scss`
- Create: `frontend/src/app/views/rewatch/rewatch.spec.ts`
- Modify: `frontend/src/app/views/rewatch/README.md` (replace the M0 stub text)

**Interfaces:**
- Consumes: Task 8's `RewatchFacade` (`cards`, `isLoading`, `error`, `reload`).
- Produces: the `Rewatch` standalone component, `selector: 'app-rewatch'`.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/app/views/rewatch/rewatch.spec.ts`:

```ts
/** The §7.1 card grid and its four states (FR-RW-06/07). */
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { RewatchFacade } from '../../domain/rewatch/facade';
import type { RewatchCardVm } from '../../domain/rewatch/model';
import { Rewatch } from './rewatch';

const HEAT: RewatchCardVm = {
  id: 'f1',
  title: 'Heat',
  year: 1995,
  posterImage: null,
  ratingStars: ['star', 'star', 'star', 'star', 'star_border'],
  ratingLabel: 'Average rating: 4.0 out of 5',
  isFavorite: true,
  dueLabel: 'Overdue by 5 days',
};

async function render(
  cards: readonly RewatchCardVm[],
  isLoading = false,
  error: unknown = undefined,
): Promise<HTMLElement> {
  // The favourite test renders twice; without the reset the second
  // `configureTestingModule` throws because a component already exists.
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    imports: [Rewatch],
    providers: [
      provideRouter([]),
      {
        provide: RewatchFacade,
        useValue: {
          cards: signal(cards),
          isLoading: signal(isLoading),
          error: signal(error),
          reload: (): void => undefined,
        },
      },
    ],
  });
  const fixture = TestBed.createComponent(Rewatch);
  await fixture.whenStable();
  return fixture.nativeElement as HTMLElement;
}

describe('Rewatch view', () => {
  it('renders a card per due film', async () => {
    const element = await render([HEAT]);

    expect(element.querySelectorAll('.rewatch__card')).toHaveLength(1);
    expect(element.textContent).toContain('Heat');
    expect(element.textContent).toContain('1995');
    expect(element.textContent).toContain('Overdue by 5 days');
  });

  it('links each card to the film detail view', async () => {
    const element = await render([HEAT]);

    expect(element.querySelector('a')?.getAttribute('href')).toBe('/film/f1');
  });

  it('marks a favourite and leaves a non-favourite unmarked', async () => {
    const favourite = await render([HEAT]);
    expect(favourite.querySelector('.rewatch__favorite')).not.toBeNull();

    const plain = await render([{ ...HEAT, isFavorite: false }]);
    expect(plain.querySelector('.rewatch__favorite')).toBeNull();
  });

  it('shows a dash rather than empty stars for an unrated film', async () => {
    // FR-RAT-13: five empty stars would read as "rated zero".
    const element = await render([{ ...HEAT, ratingStars: null, ratingLabel: 'Not rated' }]);

    expect(element.querySelector('.rewatch__rating')?.textContent).toContain('—');
  });

  it('shows a loading state while the list is in flight', async () => {
    const element = await render([], true);

    expect(element.querySelector('[role="status"]')).not.toBeNull();
  });

  it('shows an empty state when nothing is due', async () => {
    // FR-RW-06: an empty due-list is a normal answer, not an error.
    const element = await render([]);

    expect(element.textContent).toContain('Nothing due right now');
    expect(element.querySelector('[role="alert"]')).toBeNull();
  });

  it('shows a non-blocking error without hiding the cards it already has', async () => {
    // FR-RW-07: the error is additive — the last successful run stays on screen.
    const element = await render([HEAT], false, new Error('boom'));

    expect(element.querySelector('[role="alert"]')).not.toBeNull();
    expect(element.querySelectorAll('.rewatch__card')).toHaveLength(1);
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && npm test -- views/rewatch`
Expected: FAIL — cannot resolve `./rewatch`

- [ ] **Step 3: Write the component**

Create `frontend/src/app/views/rewatch/rewatch.ts`:

```ts
/**
 * The Rewatch Suggestion view (REQ §7.1) — the films that are due for another
 * watch, most overdue first.
 *
 * Per §6.1 the view calls the facade only and holds no rules: the join, the
 * ordering and the card shaping all happen in `domain/rewatch/`, so this file
 * is the template's four states and nothing else.
 *
 * There is deliberately no refresh control (§7.1) — the list re-reads when the
 * view opens, and the backend recomputes once a day (§5.8).
 */
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { RouterLink } from '@angular/router';

import { RewatchFacade } from '../../domain/rewatch/facade';

@Component({
  selector: 'app-rewatch',
  imports: [MatButtonModule, MatCardModule, MatIconModule, MatProgressBarModule, RouterLink],
  templateUrl: './rewatch.html',
  styleUrl: './rewatch.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Rewatch {
  private readonly rewatch = inject(RewatchFacade);

  protected readonly cards = this.rewatch.cards;
  protected readonly isLoading = this.rewatch.isLoading;
  protected readonly error = this.rewatch.error;

  protected reload(): void {
    this.rewatch.reload();
  }
}
```

- [ ] **Step 4: Write the template**

Create `frontend/src/app/views/rewatch/rewatch.html`:

```html
<h2 class="rewatch__heading">Rewatch</h2>

@if (isLoading()) {
  <p class="rewatch__state" role="status">Looking for films that are due…</p>
  <mat-progress-bar mode="indeterminate" aria-hidden="true" />
}

<!-- FR-RW-07: the error sits above the grid rather than replacing it, so a
     failed refresh never takes the last successful run off the screen. -->
@if (error()) {
  <div class="rewatch__state rewatch__state--error" role="alert">
    <p>The suggestions could not be loaded. Is the backend running?</p>
    <button matButton type="button" (click)="reload()">Try again</button>
  </div>
}

@if (cards().length > 0) {
  <ul class="rewatch__grid">
    @for (card of cards(); track card.id) {
      <li>
        <a class="rewatch__link" [routerLink]="['/film', card.id]">
          <mat-card class="rewatch__card">
            @if (card.posterImage) {
              <img class="rewatch__poster" [src]="card.posterImage" [alt]="'Poster of ' + card.title" />
            } @else {
              <div class="rewatch__poster rewatch__poster--empty" aria-hidden="true">
                <mat-icon>movie</mat-icon>
              </div>
            }
            <div class="rewatch__body">
              <h3 class="rewatch__title">
                {{ card.title }}
                @if (card.isFavorite) {
                  <mat-icon class="rewatch__favorite" aria-label="Favourite">favorite</mat-icon>
                }
              </h3>
              <p class="rewatch__year">{{ card.year }}</p>
              <p class="rewatch__rating" [attr.aria-label]="card.ratingLabel">
                @if (card.ratingStars) {
                  @for (icon of card.ratingStars; track $index) {
                    <mat-icon aria-hidden="true" inline>{{ icon }}</mat-icon>
                  }
                } @else {
                  <span aria-hidden="true">&mdash;</span>
                }
              </p>
              <p class="rewatch__due">
                <mat-icon aria-hidden="true" inline>schedule</mat-icon>
                {{ card.dueLabel }}
              </p>
            </div>
          </mat-card>
        </a>
      </li>
    }
  </ul>
} @else if (!isLoading() && !error()) {
  <p class="rewatch__state">Nothing due right now. Enjoy the backlog.</p>
}
```

- [ ] **Step 5: Write the styles**

Create `frontend/src/app/views/rewatch/rewatch.scss`:

```scss
/* Rewatch view (REQ §7.1). Colours come from Material's M3 system variables,
   which resolve per `color-scheme` — so light/dark needs no rule of its own. */

.rewatch__heading {
  font: var(--mat-sys-headline-small);
  margin: 0 0 1rem;
}

.rewatch__state {
  color: var(--mat-sys-on-surface-variant);
}

.rewatch__state--error {
  color: var(--mat-sys-error);
}

/* The §7.1 responsive card grid: as many columns as fit, one on a phone. */
.rewatch__grid {
  display: grid;
  gap: 1rem;
  grid-template-columns: repeat(auto-fill, minmax(11rem, 1fr));
  list-style: none;
  margin: 0;
  padding: 0;
}

.rewatch__link {
  color: inherit;
  display: block;
  text-decoration: none;
}

.rewatch__card {
  height: 100%;
  overflow: hidden;
  padding: 0;
}

.rewatch__poster {
  aspect-ratio: 2 / 3;
  display: block;
  max-width: 100%;
  object-fit: cover;
  width: 100%;
}

.rewatch__poster--empty {
  align-items: center;
  background: var(--mat-sys-surface-container-high);
  color: var(--mat-sys-on-surface-variant);
  display: flex;
  justify-content: center;
}

.rewatch__body {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.75rem;
}

/* §7.1: the title is truncated with an ellipsis rather than wrapping, so every
   card in a row keeps the same height. */
.rewatch__title {
  align-items: center;
  display: flex;
  font: var(--mat-sys-title-small);
  gap: 0.25rem;
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rewatch__favorite {
  color: var(--mat-sys-primary);
  flex: none;
}

.rewatch__year,
.rewatch__rating,
.rewatch__due {
  color: var(--mat-sys-on-surface-variant);
  font: var(--mat-sys-body-small);
  margin: 0;
}
```

- [ ] **Step 6: Replace the view README**

Replace the entire contents of `frontend/src/app/views/rewatch/README.md`:

```markdown
# `views/rewatch/`

The Rewatch Suggestion view (REQ §7.1, DESIGN §6.3) — a responsive card grid of
the films currently due for a rewatch, most overdue first. A primary navigation
destination and the app's landing route (§6.5).

The view holds no rules: `domain/rewatch/` joins the due-list to the cached
film metadata and shapes the cards. Ordering is the algorithm's and is never
re-sorted here (FR-RW-04). There is no refresh control by design (§7.1) —
the backend recomputes once a day, and a film the user has just watched is
removed from the list immediately by the facade (§6.3).

Not built yet: filtering the list by tag/genre/director, which DESIGN §6.3
marks as future work, not first release.
```

- [ ] **Step 7: Run the test to verify it passes**

Run: `cd frontend && npm test -- views/rewatch`
Expected: PASS — 7 passed

- [ ] **Step 8: Run the full frontend gate**

Run: `cd frontend && npm run build && npm test && npm run lint`
Expected: all green, including template a11y.

- [ ] **Step 9: Stop. Do not commit.**

---

## Task 11: Navigation and routing

**Files:**
- Modify: `frontend/src/app/core/route-registry.ts`
- Modify: `frontend/src/app/core/routes.registry.ts`
- Modify: `frontend/src/app/app.html`
- Modify: `frontend/src/app/app.scss`
- Modify: `frontend/src/app/app.ts`
- Modify: `frontend/src/app/app.spec.ts`
- Create: `frontend/src/app/core/route-registry.spec.ts`

**Interfaces:**
- Consumes: Task 10's `Rewatch` component.
- Produces: `RouteRegistryEntry.navIcon?: string`, `RouteRegistryEntry.navLabel?: string`; `NavDestination { path, icon, label }`; `navDestinations(registry): readonly NavDestination[]`.

**Deviation from the spec, restated:** the drawer is a CSS-styled `<nav>`, not
`mat-sidenav`. A permanently-open drawer that never toggles is a static
sidebar; `mat-sidenav` would add a container element, a breakpoint observer and
a `mode` binding to render the same thing.

- [ ] **Step 1: Write the failing registry test**

Create `frontend/src/app/core/route-registry.spec.ts`:

```ts
/** Nav destinations are derived from the registry, so registering a route stays the single wiring point (FR-EXT-02). */
import { navDestinations, type RouteRegistryEntry } from './route-registry';
import { ROUTE_REGISTRY } from './routes.registry';

const load = (): Promise<never> => Promise.reject(new Error('not loaded in tests'));

describe('navDestinations', () => {
  it('includes only entries carrying both nav fields', () => {
    const registry: readonly RouteRegistryEntry[] = [
      { path: 'a', title: 'A', loadComponent: load, navIcon: 'star', navLabel: 'Alpha' },
      { path: 'b', title: 'B', loadComponent: load },
    ];

    expect(navDestinations(registry)).toEqual([{ path: 'a', icon: 'star', label: 'Alpha' }]);
  });

  it('excludes a redirect entry, which mounts no component', () => {
    const registry: readonly RouteRegistryEntry[] = [
      { path: '', title: 'A', redirectTo: 'a' },
      { path: 'a', title: 'A', loadComponent: load, navIcon: 'star', navLabel: 'Alpha' },
    ];

    expect(navDestinations(registry).map((item) => item.path)).toEqual(['a']);
  });

  it('keeps the registry order', () => {
    const registry: readonly RouteRegistryEntry[] = [
      { path: 'a', title: 'A', loadComponent: load, navIcon: 'i', navLabel: 'A' },
      { path: 'b', title: 'B', loadComponent: load, navIcon: 'i', navLabel: 'B' },
    ];

    expect(navDestinations(registry).map((item) => item.path)).toEqual(['a', 'b']);
  });
});

describe('ROUTE_REGISTRY', () => {
  it('exposes exactly the two §6.5 primary destinations', () => {
    expect(navDestinations(ROUTE_REGISTRY).map((item) => item.label)).toEqual(['Rewatch', 'Library']);
  });

  it('never exposes the contextual film detail route', () => {
    expect(navDestinations(ROUTE_REGISTRY).map((item) => item.path)).not.toContain('film/:id');
  });

  it('redirects the root path to the Rewatch view', () => {
    // A redirect, not a second mount: `/` must resolve to the URL the
    // navigation links to, or it would mark no destination active.
    expect(ROUTE_REGISTRY.find((entry) => entry.path === '')?.redirectTo).toBe('rewatch');
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && npm test -- route-registry`
Expected: FAIL — `navDestinations` is not exported.

- [ ] **Step 3: Extend the registry interface**

In `frontend/src/app/core/route-registry.ts`, add the two optional fields to
`RouteRegistryEntry` (after `title`) and append the helper:

```ts
  /**
   * Material icon for the navigation element (§6.5). Present together with
   * `navLabel` on exactly the primary destinations — an entry carrying both is
   * what makes it one, so `film/:id` (contextual) needs no opt-out.
   */
  readonly navIcon?: string;
  /** Navigation label, shown beside `navIcon`. */
  readonly navLabel?: string;
  /**
   * Set instead of `loadComponent` to make this path a redirect — the landing
   * route (§6.5) points at the Rewatch view this way rather than mounting the
   * component a second time, which would leave `/` matching no navigation
   * entry and so marking none of them active.
   */
  readonly redirectTo?: string;
```

Make `loadComponent` optional in the same interface (`readonly loadComponent?: () => Promise<Type<unknown>>;`), since a redirect entry has none, and teach `buildRoutes` about it:

```ts
/** Projects the registry into the `Routes` array the Angular router consumes. */
export function buildRoutes(registry: readonly RouteRegistryEntry[]): Routes {
  return registry.map(({ path, title, loadComponent, redirectTo }) =>
    redirectTo === undefined
      ? { path, title, loadComponent }
      : // `pathMatch: 'full'` so an empty path redirects only when it is the
        // whole URL, not as a prefix of every other route.
        { path, redirectTo, pathMatch: 'full' as const },
  );
}
```

```ts
/** One entry of the navigation element (§6.5). */
export interface NavDestination {
  readonly path: string;
  readonly icon: string;
  readonly label: string;
}

/** The registry's primary navigation destinations, in registry order (§6.5, FR-EXT-02). */
export function navDestinations(registry: readonly RouteRegistryEntry[]): readonly NavDestination[] {
  return registry.flatMap((entry) =>
    entry.navIcon !== undefined && entry.navLabel !== undefined
      ? [{ path: entry.path, icon: entry.navIcon, label: entry.navLabel }]
      : [],
  );
}
```

- [ ] **Step 4: Register the Rewatch view**

Replace the body of `frontend/src/app/core/routes.registry.ts` below the
`import` (keep the file's doc comment, extend it if needed):

```ts
const rewatch = (): Promise<typeof import('../views/rewatch/rewatch').Rewatch> =>
  import('../views/rewatch/rewatch').then((module) => module.Rewatch);

const library = (): Promise<typeof import('../views/library/library').Library> =>
  import('../views/library/library').then((module) => module.Library);

const filmDetail = (): Promise<typeof import('../views/film-detail/film-detail').FilmDetail> =>
  import('../views/film-detail/film-detail').then((module) => module.FilmDetail);

export const ROUTE_REGISTRY: readonly RouteRegistryEntry[] = [
  // Rewatch is the landing route: it is the primary discovery view (§6.5).
  // A redirect rather than a second mount, so `/` resolves to the same URL the
  // navigation links to and the active marker has one path to match.
  { path: '', title: 'Rewatch', redirectTo: 'rewatch' },
  { path: 'rewatch', title: 'Rewatch', loadComponent: rewatch, navIcon: 'replay', navLabel: 'Rewatch' },
  { path: 'library', title: 'Library', loadComponent: library, navIcon: 'video_library', navLabel: 'Library' },
  // Reached by selecting a film, never from the navigation (§6.5).
  { path: 'film/:id', title: 'Film', loadComponent: filmDetail },
];
```

- [ ] **Step 5: Write the failing shell test**

Replace `frontend/src/app/app.spec.ts` entirely:

```ts
/** The app shell: the title, the theme control, and the §6.5 navigation. */
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { App } from './app';

async function render(): Promise<HTMLElement> {
  TestBed.configureTestingModule({
    imports: [App],
    providers: [provideRouter([])],
  });
  const fixture = TestBed.createComponent(App);
  await fixture.whenStable();
  return fixture.nativeElement as HTMLElement;
}

describe('App', () => {
  it('renders the app title', async () => {
    expect((await render()).querySelector('h1')?.textContent).toContain('Film Rewatch');
  });

  it('renders both primary destinations in the navigation', async () => {
    const links = (await render()).querySelectorAll('nav a');

    expect([...links].map((link) => link.textContent?.trim())).toEqual(['Rewatch', 'Library']);
  });

  it('points each destination at its own route', async () => {
    const links = (await render()).querySelectorAll('nav a');

    expect([...links].map((link) => link.getAttribute('href'))).toEqual(['/rewatch', '/library']);
  });

  it('labels the navigation landmark', async () => {
    expect((await render()).querySelector('nav')?.getAttribute('aria-label')).toBe('Primary');
  });
});
```

- [ ] **Step 6: Run it to verify it fails**

Run: `cd frontend && npm test -- app.spec`
Expected: FAIL — no `nav` element.

- [ ] **Step 7: Write the shell component**

In `frontend/src/app/app.ts`, replace the doc comment's second paragraph,
add the imports, and expose the destinations:

```ts
/**
 * Root component — the app bar, the §6.5 navigation, and the router outlet.
 *
 * The navigation adapts by viewport in CSS alone (`app.scss`): a bottom bar on
 * a phone, a permanent left sidebar from 900px up. The design names
 * `mat-sidenav mode="side"` for the wide case, but a drawer that is always open
 * and never toggles is a static sidebar — the container, the breakpoint
 * observer and the `mode` binding would all render the same thing.
 */
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatIconModule } from '@angular/material/icon';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { navDestinations } from './core/route-registry';
import { ROUTE_REGISTRY } from './core/routes.registry';
import { ThemeService } from './core/theme';

@Component({
  selector: 'app-root',
  imports: [MatButtonToggleModule, MatIconModule, RouterLink, RouterLinkActive, RouterOutlet],
  templateUrl: './app.html',
  styleUrl: './app.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class App {
  protected readonly title = signal('Film Rewatch');
  protected readonly theme = inject(ThemeService).preference;
  /** Derived from the registry, so registering a route stays the one wiring point (FR-EXT-02). */
  protected readonly destinations = navDestinations(ROUTE_REGISTRY);
}
```

- [ ] **Step 8: Write the shell template**

Replace `frontend/src/app/app.html` entirely:

```html
<nav class="app-nav" aria-label="Primary">
  @for (destination of destinations; track destination.path) {
    <a
      class="app-nav__link"
      routerLinkActive="app-nav__link--active"
      #active="routerLinkActive"
      [routerLink]="['/', destination.path]"
      [attr.aria-current]="active.isActive ? 'page' : null"
    >
      <mat-icon aria-hidden="true">{{ destination.icon }}</mat-icon>
      <span class="app-nav__label">{{ destination.label }}</span>
    </a>
  }
</nav>

<div class="app-shell">
  <header class="app-bar">
    <h1 class="app-bar__title">{{ title() }}</h1>
    <mat-button-toggle-group
      class="app-bar__theme"
      aria-label="Colour theme"
      hideSingleSelectionIndicator
      [value]="theme()"
      (valueChange)="theme.set($event)"
    >
      <mat-button-toggle value="light">Light</mat-button-toggle>
      <mat-button-toggle value="dark">Dark</mat-button-toggle>
      <mat-button-toggle value="auto">Auto</mat-button-toggle>
    </mat-button-toggle-group>
  </header>

  <main class="app-main">
    <router-outlet />
  </main>
</div>
```

- [ ] **Step 9: Write the shell styles**

Append to `frontend/src/app/app.scss` (and change `.app-main` as shown):

```scss
/* §6.5 navigation. Mobile-first: a fixed bottom bar, becoming a permanent left
   sidebar at the 900px breakpoint. One element, two layouts — the markup does
   not branch, only the CSS does. */
.app-nav {
  background: var(--mat-sys-surface-container);
  border-top: 1px solid var(--mat-sys-outline-variant);
  bottom: 0;
  display: flex;
  justify-content: space-around;
  left: 0;
  position: fixed;
  right: 0;
  z-index: 2;
}

.app-nav__link {
  align-items: center;
  color: var(--mat-sys-on-surface-variant);
  display: flex;
  flex-direction: column;
  font: var(--mat-sys-label-medium);
  gap: 0.125rem;
  justify-content: center;
  /* The M7 a11y pass sets the definitive figure; 48px is the floor (NFR-A11Y). */
  min-height: 48px;
  min-width: 48px;
  padding: 0.5rem 1rem;
  text-decoration: none;
}

.app-nav__link--active {
  color: var(--mat-sys-primary);
}

.app-main {
  margin: 0 auto;
  max-width: 60rem;
  /* Clear the fixed bottom bar so the last row is never hidden behind it. */
  padding: 1.5rem 1rem 5rem;
}

@media (min-width: 900px) {
  .app-nav {
    border-right: 1px solid var(--mat-sys-outline-variant);
    border-top: none;
    flex-direction: column;
    justify-content: flex-start;
    padding-top: 1rem;
    right: auto;
    top: 0;
    width: 14rem;
  }

  .app-nav__link {
    align-items: center;
    flex-direction: row;
    gap: 0.75rem;
    justify-content: flex-start;
    width: 100%;
  }

  /* The sidebar is fixed, so the content is inset rather than pushed. */
  .app-shell {
    padding-left: 14rem;
  }

  .app-main {
    padding-bottom: 1.5rem;
  }
}
```

Delete the old `.app-main` block further up the file — the one above replaces it.

- [ ] **Step 10: Run the tests to verify they pass**

Run: `cd frontend && npm test`
Expected: PASS — the whole suite, including the untouched library and
film-detail specs.

- [ ] **Step 11: Run the full frontend gate**

Run: `cd frontend && npm run build && npm test && npm run lint`
Expected: all green.

- [ ] **Step 12: Check it in a browser**

Run `npm start`, with the backend up, and confirm:
- `/` lands on Rewatch; the nav marks Rewatch active.
- `/library` still works and the nav marks Library active.
- Below 900px the nav is a bottom bar and nothing is hidden behind it; at or
  above 900px it is a left sidebar and the content is inset.
- Dark, light and auto all still render the nav legibly.

- [ ] **Step 13: Stop. Do not commit.**

---

## Task 12: Documentation

**Files:**
- Modify: `docs/requirements/OPEN_DECISIONS_V1.md`
- Modify: `backend/CLAUDE.md`
- Modify: `frontend/CLAUDE.md`
- Modify: `CLAUDE.md` (repo root)

**Interfaces:** none — documentation only.

- [ ] **Step 1: Close the M4 open decisions**

In `docs/requirements/OPEN_DECISIONS_V1.md`, replace the whole
`## M4 — Rewatch engine` section with:

```markdown
## M4 — Rewatch engine

- **[impl] Scheduler mechanism (daily rewatch job)** — **Decided (2026-09-14):**
  an in-process `asyncio` task owned by the FastAPI lifespan
  (`app/rewatch/scheduler.py`). The deployment target is a single laptop
  running one container (§1.3), where a scheduler that lives and dies with the
  app is the whole requirement — and every start recomputes, so a restart costs
  nothing. (DESIGN §5.8, §8.1.)
- **[design] Rewatch algorithm internals** — **Still open.** The repo owner
  supplies the scoring logic. A documented placeholder ships in its place
  (`app/rewatch/algorithm.py`): every film is due one year after its last
  watch, deferred by `delay_days`; `average_rating`, `watch_count` and
  `is_favorite` are accepted and ignored. The input/output contract is fixed,
  so the real algorithm replaces `suggest`'s body and nothing else.
  (DESIGN §5.8.)
```

Under `## M3 — Angular shell`, append to the responsive-breakpoints entry:

```markdown
  **Partially decided (2026-09-14):** the navigation switches between the
  bottom bar and the sidebar at `900px`. The rest of the responsive pass is
  still open.
```

- [ ] **Step 2: Refresh `backend/CLAUDE.md`**

Replace the milestone paragraph (the bold "**The repo is in M1...**" line) with:

```markdown
**M1 ("Core domain") and M4's rewatch engine are built.** The seven §5.2 tables
plus the `rewatch_suggestions` projection exist with their migrations;
`rewatch/` holds the pure algorithm, the daily in-process scheduler, and
`GET /rewatch-suggestions`. The scoring logic itself is a documented
placeholder — see `OPEN_DECISIONS_V1.md`. Do not add domain logic to a
milestone that doesn't own it.
```

In the `core/db.py` bullet under "Cross-cutting `core/`", mention
`session_scope` alongside `get_session`, and change "The seven domain models
register on `Base.metadata`" to note the projection as the eighth table and
that the guard test now expects it.

- [ ] **Step 3: Refresh `frontend/CLAUDE.md`**

Replace the milestone paragraph (the bold "**The repo is in M0...**" line) with:

```markdown
**The Rewatch, Library and Film Detail views are built**, as is the §6.5
adaptive navigation (bottom bar below 900px, permanent sidebar above). Still
ahead: the Add Film flow, search filters beyond the title search, and the
cache/sync + PWA layer (M5).
```

In the "Routing (§6.5)" section, add that an entry becomes a primary
navigation destination by carrying `navIcon` and `navLabel`, and that
`navDestinations()` is what the shell reads.

- [ ] **Step 4: Refresh the root `CLAUDE.md`**

Replace the "**The repo is currently in M1**" sentence with a line saying the
core domain and the rewatch engine are built, and that the current open item is
the real scoring algorithm. Keep the surrounding paragraph's shape and its
pointer to the milestone docs.

- [ ] **Step 5: Verify nothing else claims rewatch is unbuilt**

Run: `cd /Users/jan/Projects/FilmRewatchApp && grep -rn "arrives in M4\|arrive in M4\|empty stub\|M0 stub" --include='*.py' --include='*.ts' --include='*.md' backend/app frontend/src *.md`
Expected: no hits referring to the rewatch module. Fix any that remain.

- [ ] **Step 6: Run both gates one final time**

Run: `cd backend && make typecheck && make lint && make format-check && make test`
Run: `cd frontend && npm run build && npm test && npm run lint`
Expected: both green.

- [ ] **Step 7: Stop. Do not commit.**

---

## Self-review notes

Checked against the spec:

- §2 open decisions → Task 12. §3.2 algorithm → Task 1. §3.3 projection → Task 2.
  §3.4 repository → Task 3. §3.5 service → Task 4. §3.6 scheduler → Task 6.
  §3.7 schemas/router → Task 5. §3.8 backend tests → spread across Tasks 1-6.
  §4.1 domain layer → Task 8. §4.2 optimistic removal → Task 9. §4.3 view →
  Task 10. §4.4 navigation + §4.5 routing → Task 11. §4.6 frontend tests →
  Tasks 7-11. §5 documentation → Task 12, with the `main.py` version bump
  folded into Task 5 where that file is already open.
- Two spec items are deliberately reshaped and flagged above: the algorithm
  dataclass names, and CSS navigation instead of `mat-sidenav`.
- Two guard tests the spec did not anticipate must be widened, or Task 2 fails:
  `test_db_plumbing.py`'s metadata assertion and `test_db_harness.py`'s table
  assertion. A third, `test_openapi_contract.py`'s `_M1_ROUTES`, must gain the
  new route in Task 5.
- `app.spec.ts` currently has no `provideRouter`; Task 11 adds it, which the
  `routerLink`s require.
