# Rewatch View — M4 Design

**Date:** 2026-09-14
**Status:** Approved
**Implements:** DESIGN_V1 §5.8, §6.3, §6.5, §7.1 · REQUIREMENTS_V1 FR-RW-01..07, §7.1
**Milestone:** M4 (Rewatch engine), plus the §6.5 navigation element deferred from M3.

---

## 1. Scope

The full M4 vertical: the backend rewatch engine (pure algorithm, projection
table, daily scheduler, endpoint), the client's data and business-logic layers
for it, the Rewatch Suggestion view, and the navigation element that makes the
app's two primary destinations reachable.

**In scope**

- `app/rewatch/` completed from M0 stubs to a working feature module.
- `rewatch_suggestions` projection table + Alembic migration.
- A **placeholder** scoring algorithm behind the fixed FR-RW-01/03 contract.
- In-process daily scheduler.
- `GET /api/v1/rewatch-suggestions`.
- Client `domain/rewatch/` + `views/rewatch/` + optimistic removal on watch.
- §6.5 navigation: desktop drawer, mobile bottom bar.

**Out of scope**

- The real scoring logic. The repo owner supplies it later; this design fixes
  the contract so it drops in as a one-file swap (FR-EXT-09).
- Rewatch list **filtering** (DESIGN §6.3 marks it future, not first release).
- IndexedDB caching of the due-list and offline behaviour — that is M5
  (§6.2/§6.4). This design consumes the endpoint over plain HTTP; the
  cache/sync module slots in behind the data layer later without touching the
  view.
- Manual refresh. There is none by design (§7.1).

---

## 2. Open decisions closed here

Both M4 entries in `OPEN_DECISIONS_V1.md`:

| Decision | Resolution |
| --- | --- |
| **[impl] Scheduler mechanism** | In-process `asyncio` task started in the FastAPI lifespan. No new container, no new dependency. Fits the single-laptop deployment target (§1.3). |
| **[design] Rewatch algorithm internals** | Deferred by the owner. A documented placeholder ships in its place; the input/output contract is what this design fixes. |

The M3 entry **[design] Responsive breakpoints** is partially closed: the
navigation switches at `900px`. The full responsive pass (§7.4) stays open.

---

## 3. Backend

### 3.1 Module layout

`app/rewatch/` follows the §5.1 layering already used by films/ratings/tags/
genres: a router that never imports a repository, a service that owns the
business logic, a repository that owns persistence.

```
app/rewatch/
├── algorithm.py    NEW — pure scoring, no app imports
├── models.py       the rewatch_suggestions projection
├── repository.py   replace_all / list_all
├── schemas.py      the wire DTOs
├── service.py      FR-RW-02 payload assembly + persistence
├── scheduler.py    NEW — the daily trigger
└── router.py       GET /rewatch-suggestions
```

### 3.2 `algorithm.py` — the pure module

Imports only the standard library. No SQLAlchemy, no FastAPI, no `app.*`
imports — this is what makes §3.3 isolation checkable rather than aspirational.

```python
@dataclass(frozen=True)
class RewatchInput:          # exactly the FR-RW-02 table
    film_id: UUID
    average_rating: Decimal | None
    watch_count: int
    last_watched_date: date
    is_favorite: bool
    delay_days: int

@dataclass(frozen=True)
class RewatchSuggestion:     # exactly the FR-RW-03 table
    film_id: UUID
    days_until_next_rewatch: int

def suggest(inputs: Sequence[RewatchInput], today: date) -> list[RewatchSuggestion]: ...
```

**Placeholder logic.**

```
interval    = BASE_INTERVAL_DAYS + delay_days      # BASE_INTERVAL_DAYS = 365
due_date    = last_watched_date + interval
days_until  = (due_date - today).days
```

Keep entries with `days_until <= 0`; sort ascending by `days_until`, ties broken
by `film_id` so the order is deterministic across runs. `average_rating`,
`watch_count` and `is_favorite` are accepted and deliberately unused — the real
algorithm will use them, and the signature must not change when it arrives.

The placeholder is marked in the module docstring and with a `ponytail:` comment
naming the ceiling (every film is simply due a year after its last watch) and
the upgrade path (replace `suggest`'s body; nothing else moves).

### 3.3 `models.py` — the projection

| Column | Type | Notes |
| --- | --- | --- |
| `film_id` | UUID, PK | FK → `films.id`, `ON DELETE CASCADE`. One row per due film, so the film id is the natural key. |
| `days_until_next_rewatch` | Integer | `<= 0` by the FR-RW-03 contract. |
| `position` | Integer | The algorithm's order, stored verbatim. |
| `computed_at` | DateTime (tz) | When the run that produced this row finished. |

`position` exists rather than re-deriving order from `days_until_next_rewatch`
at read time: FR-RW-04 forbids anyone downstream re-sorting, and a future
algorithm may order by an internal score whose ties are meaningful. Storing the
order is one column and removes the question.

### 3.4 `repository.py`

- `replace_all(rows)` — deletes every row and inserts the new list inside one
  transaction. The projection is whole-list-replaced, never patched.
- `list_all()` — every row ordered by `position` ascending.

### 3.5 `service.py`

`recompute(today)`:

1. One aggregate query over films + ratings producing, per film:
   `film_id`, `AVG(value)` over rated entries only (NULL when none are rated —
   FR-RAT-11/12), `COUNT(*)` as `watch_count`, `MAX(watch_date)` as
   `last_watched_date`, plus `is_favorite` and `delay_days` from `films`.
   Every film has ≥ 1 rating (FR-LIB-03), so `last_watched_date` is never null.
2. Map rows to `RewatchInput`.
3. Call `algorithm.suggest(inputs, today)`.
4. `repository.replace_all(...)` with `position` = list index.

`list_suggestions()` reads the stored projection for the router. The service
never knows what triggered it.

### 3.6 `scheduler.py`

An `asyncio` task owned by the FastAPI lifespan:

```
on startup:  recompute once, then loop { sleep REWATCH_RECOMPUTE_INTERVAL; recompute }
on shutdown: cancel the task
```

Every iteration wraps `recompute` in try/except and logs failures — a failed run
must not kill the loop or the app. A failed run leaves the previous projection
in place, which is what FR-RW-07 wants: the client keeps showing the last good
list. `main.py` gains `lifespan=` on the app factory. The interval is a setting
`REWATCH_RECOMPUTE_INTERVAL_SECONDS` in `core/config.py` (default 86400) so
tests can shorten it. The cadence is "24h since the last run", not a wall-clock
time of day — the §5.8 contract only requires once-daily, and an interval sleep
needs no timezone reasoning.

### 3.7 `schemas.py` / `router.py`

`GET /api/v1/rewatch-suggestions` → `list[RewatchSuggestionRead]`, each
`{ "film_id", "days_until_next_rewatch" }`. A bare JSON array, matching
`GET /films` and `GET /tags`, which return `list[...]` with no envelope. Order
is the stored order. The endpoint never recomputes (§5.8) and takes no parameters.

The response deliberately carries no film metadata: the client already holds the
whole library from `GET /films` and joins locally (§6.3).

### 3.8 Backend tests

- `algorithm.py` in isolation: due / overdue / not-yet-due boundaries, ordering
  (most overdue first), `delay_days` pushing a film out, tie determinism,
  empty input. No DB, no fixtures.
- `service.recompute` against the test DB: the aggregate is right for a film
  with unrated watches, `replace_all` leaves no stale rows from a prior run.
- The endpoint via TestClient: empty projection → `{"items": []}`, populated →
  stored order preserved.

---

## 4. Frontend

### 4.1 `domain/rewatch/`

Mirrors `domain/film/`:

- `api.ts` — an `httpResource` over `GET /rewatch-suggestions`, plus the DTO type.
- `model.ts` — `RewatchSuggestion { filmId, daysUntilNextRewatch }` and the
  view model `RewatchCardVm { id, title, year, posterImage, ratingStars,
  ratingLabel, isFavorite, dueLabel }`.
- `mapper.ts` — DTO → domain, and the `dueLabel` wording: `0` → `"Due now"`,
  negative → `"Overdue by N days"` (`"Overdue by 1 day"` singular).
- `facade.ts` — the single API the view calls. Joins each suggestion's `filmId`
  to `FilmFacade.films` and projects `RewatchCardVm[]`, **preserving the
  suggestion order** (FR-RW-04) and skipping any id the library doesn't hold.
  Exposes `isLoading`, `error`, and `removeFilm(id)`.

`removeFilm` mutates the resource's value signal locally, the same pattern
`FilmFacade` already uses for its local writes.

### 4.2 Optimistic removal (§6.3)

`RatingFacade.add()` gains one more `tap`: after `films.applyRatingAdded(...)`,
call `rewatch.removeFilm(filmId)`. A freshly watched film leaves the due-list
immediately, from wherever the watch was logged. The daily job stays
authoritative and restores the film at the next fetch if it really is still due.

`RatingFacade` injecting `RewatchFacade` is a sideways call inside the
business-logic layer, which §6.1 permits — the same shape as its existing
`FilmFacade` dependency.

### 4.3 `views/rewatch/`

A responsive card grid (CSS grid, `auto-fill` + `minmax`). Per §7.1 the card
shows poster (or the `movie` icon placeholder the library already uses), title
(ellipsis-truncated), release year, average rating as stars with an em-dash
placeholder when unrated (FR-RAT-13), a favourite icon only when `true`, and the
rewatch status. The whole card is a `routerLink` to `/film/:id`.

Four states:

| State | Render |
| --- | --- |
| Loading | A progress indicator, `role="status"`. |
| Empty (FR-RW-06) | "Nothing due right now." — not an error. |
| Error (FR-RW-07) | A non-blocking `role="alert"` banner **above the cards**. If a previous successful run's cards are in hand they stay rendered; the rest of the app is unaffected. |
| Populated | The grid. |

The view re-reads on open; there is no refresh control (§7.1).

### 4.4 Navigation (§6.5)

The app shell (`app.html`) currently holds a title and a theme toggle. It gains
the navigation element, switching at **900px**:

- **≥ 900px — permanent drawer.** `mat-sidenav` with `mode="side"` pinned open,
  pushing content beside it. Entries are icon + text label.
- **< 900px — bottom navigation bar.** A fixed bar with the same two
  destinations as icon + label. Targets are at least 48×48px; the definitive
touch-target figure is set in the M7 a11y pass.

Two primary destinations only — **Rewatch** and **Library** (§6.5). Film Detail
is contextual and never appears in navigation. The active destination is marked
visually and with `aria-current="page"`.

The destination list is derived from the route registry rather than hand-written,
so registering a route is still the single place a view is wired (FR-EXT-02).
`RouteRegistryEntry` gains two optional fields — `navIcon` and `navLabel` — and
an entry is a navigation destination exactly when it has them. `film/:id` and the
`''` alias have neither, so they never render.

### 4.5 Routing

| Path | View | Note |
| --- | --- | --- |
| `''` | Rewatch | The landing route, as §6.5 intends. Replaces the Library placeholder and its "until the Rewatch view exists" comment. |
| `rewatch` | Rewatch | Nav destination. |
| `library` | Library | Nav destination. |
| `film/:id` | Film Detail | Contextual. |

### 4.6 Frontend tests

- `mapper` — the `dueLabel` wording including the 1-day singular.
- `facade` — the join preserves suggestion order, skips unknown ids,
  `removeFilm` drops exactly one entry.
- `RatingFacade` — adding a rating removes the film from the due-list.
- The view — each of the four states, and that the error state keeps prior cards.
- Navigation — both destinations render from the registry, the active one is
  marked, `film/:id` never appears.

---

## 5. Documentation updates

- `OPEN_DECISIONS_V1.md` — close both M4 entries with their resolutions; note
  the nav breakpoint against the M3 responsive entry, which stays open.
- `frontend/src/app/views/rewatch/README.md` — replace the M0 stub text.
- `backend/app/rewatch/` module docstrings — drop "arrives in M4" throughout.
- `frontend/src/app/core/routes.registry.ts` — the landing-route comment.
- `backend/app/main.py` — the `build_api_router` docstring still calls rewatch
  an empty stub.
- App `version` bump in `main.py` (0.2.0 → 0.3.0): new backwards-compatible
  API surface.

No milestone document. The repo has M0 and M1 only; M2 and M3 shipped without
one and this design does not reintroduce the practice.

---

## 6. Risks

- **The placeholder will look wrong.** With a 365-day base interval and a fresh
  library, the due-list may well be empty on first run. That is correct
  behaviour, not a bug, and the empty state is what it should show. Seeding a
  film with an old `watch_date` is how to see cards.
- **The scheduler dies with the process.** Accepted: on the single-laptop
  target the app is the only thing running, and a recompute happens at every
  boot.
- **The `''` route changing owner** will surprise anyone with the Library
  bookmarked at the root. `/library` keeps working.
