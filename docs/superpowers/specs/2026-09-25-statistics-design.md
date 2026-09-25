# Statistics view — design

Date: 2026-09-25 · Status: approved in chat, pending spec review

## Goal

A Statistics page showing viewing statistics once for **all time** and once for **each year** since tracking began: watches, rewatches, first-time watches, films released that year, plus time watched, ratings, top lists and a per-month breakdown.

## Approach

- One backend endpoint `GET /api/v1/stats` in a new feature module `backend/app/stats/`.
- The repository loads every rating entry joined with its film's data (id, primary title, release year, runtime, director) in **one** query, plus a second query for genres — joining genres into the first query would repeat each entry once per genre.
- A dependency-free pure function in `stats/algorithm.py` (same pattern as `rewatch/algorithm.py`) computes the whole payload; it is unit-testable without a database.
- The frontend only renders. No client-side aggregation.

Rejected: per-metric SQL aggregates (~10 queries, harder to test); client-side computation (the library list carries no watch history — would need one request per film).

## Definitions

A **watch** is one rating entry, rated or not (FR-RAT-12). Entries dated `EARLIER_WATCH_DATE` (1888-01-01, "seen before, date unknown") are **undated watches**.

| Metric | Per year Y | All time |
|---|---|---|
| `watches` | Entries with `watch_date` in Y | All entries, incl. undated |
| `first_watches` | Films whose earliest entry falls in Y **and** that have no undated entry | Films whose earliest entry is dated (no undated entry) — i.e. distinct films minus films with an undated entry |
| `rewatches` | `watches − first_watches` | `watches − first_watches` |
| `films_released_that_year` | Distinct films with `release_year == Y` watched in Y | not present (`null`) |
| `distinct_films` | Distinct films watched in Y | All films |
| `minutes_watched` | Σ film runtime over the year's watches | Σ over all watches, incl. undated |
| `average_rating` | Mean of non-null values in Y; `null` if none | Mean of all non-null values |
| `rating_distribution` | Count per value 0.5…5.0 (10 buckets, zeros included), non-null only | same, all time |
| `top_genres` | Top 5 genres by `score = watches × average_rating` of the genre's rated watches (name + watches + average_rating + score); a watch counts once per genre of its film. Unrated watches count in `watches` but are never imputed a rating value, so a genre with no rated watch in the block has no score and is excluded | same, all time |
| `top_directors` | Same rule as `top_genres`, keyed by director | same, all time |
| `top_films` | Same rule, keyed by film (id + primary title + watches + average_rating + score) | same, all time |
| `buckets` | 12 month buckets (Jan–Dec) with watch counts | One bucket per tracked year |

Rules:

- Top lists order by score desc, then average_rating desc, then name/title asc, so output is deterministic.
- The year list runs from the earliest **dated** watch's year through the current year, **newest first**. Years with no watches are included (all counts zero, averages `null`, lists empty).
- With no dated watches at all, `years` is empty.
- Undated entries count only in all-time metrics, never in any year.

## API

`GET /api/v1/stats` → `200`

```json
{
  "total": { ...StatsBlock, "films_released_that_year": null },
  "years": [ { "year": 2026, ...StatsBlock }, ... ]
}
```

`StatsBlock`: `watches`, `first_watches`, `rewatches`, `films_released_that_year`, `distinct_films`, `minutes_watched`, `average_rating`, `rating_distribution` (`[{value, count}]`), `top_genres` / `top_directors` (`[{name, watches, average_rating, score}]`), `top_films` (`[{film_id, title, watches, average_rating, score}]`), `buckets` (`[{label, count}]` — `"1"`…`"12"` for months, `"2025"` for years).

## Frontend

- `domain/stats/` — `model.ts`, `api.ts`, `mapper.ts`, `facade.ts` (§6.1: DTO → domain → view).
- `views/stats/` — the page, registered in `core/routes.registry.ts` as `{ path: 'stats', title: 'Statistics', navIcon: 'bar_chart', navLabel: 'Statistics' }` → third navigation destination.
- Layout, top to bottom:
  1. Scope switcher — a single-select `mat-button-toggle-group`: **All time · 2026 · 2025 · …** (UI copy is English, like the other views); the current year is preselected. (A `mat-chip-listbox` was tried first, but a non-selectable selected chip loses `aria-selected`, so the switcher moved to the single-select toggle group.)
  2. KPI tiles — watches, first watches, rewatches, films released that year (year scope only), hours watched, distinct films.
  3. Bar chart of `buckets` in plain CSS (no chart library); the all-time chart shows two-digit year labels (`'05`) to keep 12+ tracked years from overlapping at phone width, with the full year still in each bar's `aria-label`.
  4. Ratings — average plus distribution as small bars.
  5. Top lists — genres, directors, films; film titles link to `film/:id`.
- An empty year shows "No watches this year" instead of zero tiles.
- Colours via `--mat-sys-*` tokens only, so Dark/Light/Auto work unchanged.

## Testing

- Backend: unit tests on `algorithm.py` (first vs. rewatch, undated entries, released-that-year, empty years, unrated entries, tie-breaking); one TestClient test for the endpoint.
- Frontend: a spec for the mapper/facade.
- Gate: pyright strict + pytest; `ng build`, `ng test`, `npm run lint`.

## Out of scope

Filters (by genre/tag), date ranges other than calendar years, export, caching of the stats response (M5 cache layer will cover reads generically).
