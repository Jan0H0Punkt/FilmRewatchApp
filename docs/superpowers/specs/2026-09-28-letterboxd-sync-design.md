# Letterboxd sync — design

Date: 2026-09-28 · Status: approved in chat, pending spec review

## Goal

The user keeps logging films on Letterboxd. Every diary entry logged there shows up in this app too — without a second manual entry. One-way only: **Letterboxd → app**.

Nothing is written without the user's approval: every new entry lands in a **review list**. Where the app already has the film, the entry carries it as a suggestion and one click approves it; where it cannot place the film, the user creates it and adds the missing data (director, runtime, genres, tags) by hand.

## Source

Letterboxd has no open API. The source is the public RSS feed `https://letterboxd.com/<username>/rss/`:

- The **last 50 diary entries**, ordered by *log time* (not watch date — a backdated entry sits among recent ones), followed by list posts.
- Per diary entry: `guid` (`letterboxd-watch-<n>`, stable), `link` (`https://letterboxd.com/<user>/film/<slug>/[<n>/]`), `letterboxd:watchedDate`, `letterboxd:memberRating` (absent when unrated), `letterboxd:rewatch` (`Yes`/`No`), `letterboxd:filmTitle`, `letterboxd:filmYear`, `tmdb:movieId`.
- No director, runtime, genres — which is why unmatched films need the review list.

Fetched with `urllib.request` (same pattern as `films/service/poster_palette.py`), parsed with `xml.etree.ElementTree`. **No new dependency.** TMDB is not used in this step.

## Sync flow

1. Fetch the feed; keep only items that have a `letterboxd:watchedDate` (diary entries). Walk them in feed order, newest first.
2. For each entry:
   1. `guid` already in `letterboxd_entries` (any status) → **stop**.
   2. Find the film (see *Matching*).
   3. Exactly one film found **and** it has a watch on `watched_date` → **stop**.
   4. `watched_date` is in the future (server date; Letterboxd's date is local to the account) → **skip** without stopping; the next sync retries it.
   5. Otherwise insert the entry into `letterboxd_entries` (open), with `suggested_film_id` set when exactly one film was found and null for zero or several. Continue.
3. Record the sync time (in memory).

Rules:

- **Unrated stays unrated**: an absent `memberRating` becomes `value = NULL`, never imputed.
- The sync itself never adds a watch or edits a film; only the user's actions in the review list do.
- The `rewatch` flag does not affect entries with a suggestion; it prefills "watched before" when the user creates the film from the review list.
- Not synced in this step: rating changes to old entries, deletions on Letterboxd, entries older than the feed's 50.

Known limitation: if the app has the same watch under a different date (e.g. logged a day apart), the entry is not recognised as known and shows up for review — the user dismisses it.

## Matching

Tried in order; the first rule that yields a result decides:

1. **Letterboxd link**: the slug from the item link (`/film/<slug>/`) equals the slug of a film's `letterboxd_url` on host `letterboxd.com`. `boxd.it` short links cannot be compared and are skipped by this rule.
2. **Title + year**: `filmTitle` equals (case-insensitive, trimmed) **any** title of a film — primary or alternative — and `filmYear` equals `release_year`.

Rule 1 matching one film is decisive. Otherwise rule 2's result counts: exactly one film → suggestion; zero or several → no suggestion.

Because approving or assigning writes the canonical `letterboxd_url` onto the film (when it has none), the next entry for that film matches exactly by rule 1.

## Data

New table `letterboxd_entries` (module `app/letterboxd/`, one Alembic migration):

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `guid` | varchar(100), unique | the feed's `guid`; stop rule key |
| `film_title` | varchar(255) | |
| `film_year` | int | |
| `film_url` | varchar(2048) | canonical `https://letterboxd.com/film/<slug>/` |
| `watched_date` | date | |
| `rating` | numeric(2,1), nullable | NULL = unrated |
| `rewatch` | bool | |
| `suggested_film_id` | UUID FK → films, nullable, `ON DELETE SET NULL` | the sync's match, if exactly one |
| `created_at` | timestamptz | |
| `resolved_at` | timestamptz, nullable | NULL = open; set on assign, dismiss or auto-resolve |

Every new entry is stored. Resolved rows stay forever — they keep the stop rule working.

**Auto-resolve**: `GET /letterboxd/entries` first re-runs matching for every open entry and sets `resolved_at` on those that now match a film with a watch on `watched_date`. This is how "create film" resolves itself: the prefilled form saves the film with the Letterboxd link and the watch, and the entry disappears from the list on the next read — no extra call from the form, and it works through the offline write queue.

## Scheduling

- New setting `LETTERBOXD_USERNAME` (`core/config.py`, `.env.example`). Empty → sync is off entirely (no loop, `POST /letterboxd/sync` → `409 LETTERBOXD_DISABLED`). Tests run with it empty.
- A FastAPI `lifespan` starts one background task: every hour it checks whether the last sync is more than 24 h old (wall clock, so laptop sleep does not stall it) and, if so, runs the sync in a worker thread (`asyncio.to_thread`). The last-sync time lives only in memory, so every backend start syncs once.
- A module-level lock prevents the scheduled and the manual sync from running at the same time.
- Feed unreachable / malformed → log a warning, do not update the last-sync time; the next hourly check retries.

## API

All under `/api/v1/letterboxd`, errors in the standard envelope (NFR-MAINT-03).

| Method & path | Body | Response |
|---|---|---|
| `GET /entries` | — | `200` list of open entries, newest `watched_date` first (auto-resolve runs first) |
| `POST /entries/{id}/assign` | `{ "film_id": UUID }` | `200`; adds the watch via `FilmService.add_rating`, sets the film's `letterboxd_url` if null, resolves the entry. Used both to approve the suggestion and to pick another film. `404 NOT_FOUND` for an unknown entry or film, `409 ENTRY_RESOLVED` if already resolved |
| `POST /entries/{id}/dismiss` | — | `204`; resolves without adding anything. Same `404`/`409` |
| `POST /sync` | — | `200 { "queued": n }`; runs a sync now. `409 LETTERBOXD_DISABLED` when no username, `502 LETTERBOXD_UNAVAILABLE` when the feed cannot be read |

Entry read shape: `id`, `film_title`, `film_year`, `film_url`, `watched_date`, `rating` (nullable), `rewatch`, `suggested_film` (`{ id, title }` with the primary title, or null).

## Frontend

- `domain/letterboxd/` — `model.ts`, `api.ts`, `mapper.ts`, `facade.ts` (§6.1).
- `views/letterboxd/` — the review view, registered in `core/routes.registry.ts` with a nav entry (icon `sync`, label "Letterboxd") showing the number of open entries as a badge.
- One row per entry: title, year, watch date, rating stars (or the unrated em-dash), a link to the Letterboxd page, the suggested film (linked to its detail view) if any, and these actions:
  - **Approve** (only with a suggestion, the primary action) → `POST …/assign` with the suggested film's id.
  - **Create film** → `films/new` with query params `title`, `year`, `letterboxd_url`, `watch_date`, `rating`, `watched_before` (from `rewatch`). The film form reads them once to prefill; everything else in the form is unchanged. The user adds director, runtime, genres, tags.
  - **Assign** → dialog with a film search over the cached library list → `POST …/assign`.
  - **Dismiss** → confirm dialog → `POST …/dismiss`.
- A "Sync now" button calls `POST /letterboxd/sync` and reloads the list.
- The view needs the backend; offline it shows the FR-OFF-04 "currently unavailable" message.
- The badge count loads with the app shell and refreshes after each action in the view.

## Docs

- REQ: new §5.7 "Letterboxd Sync" with `FR-LBX-01…` covering the flow, stop rule, matching, suggestions, review list; §1.3 out-of-scope "Export or import of data" becomes "Export of data; import other than the Letterboxd sync (§5.7)"; revision 1.5.
- DESIGN: `letterboxd` module in §5.1/§5.3, the table in §5.2, the lifespan task next to §5.8, the view in §6.5.

## Testing

- `feed.py`: parser test against a trimmed copy of the real feed (diary items incl. an unrated one and a rewatch, plus a list item that must be skipped). No network.
- Service (DB tests): stop on known `guid`; stop on known watch; future date skipped; link match beats title match; title match across alternative titles; one match → suggestion, zero / several → none; the sync writes no watch; assign adds the watch and writes `letterboxd_url` only when null; auto-resolve.
- Router: each endpoint's success and error codes, with the feed fetch stubbed.
- Frontend: facade + view specs for the four actions and the film-form prefill.

## Out of scope (later)

- TMDB lookup to prefill director/runtime/poster in "Create film".
- Syncing rating changes and deletions; importing more than the feed's 50 entries.
- "Approve all" for entries with a suggestion.
