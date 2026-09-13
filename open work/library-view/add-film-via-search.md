# Add Film via the Library search

Status: **partly built** — the search half of work item 1 is done (see below);
the add half is not started. Target milestone: M3 (Library view). The repo
is in M1 — this is deliberately ahead of the milestone sequence.

Requirements covered: FR-LIB-01..05, FR-TAG-06, FR-SF-01, FR-SF-03, FR-SF-05.
Design references: REQUIREMENTS §5.1.1, §5.3, §5.4, §7.2; DESIGN §6.1, §6.5.

## The idea

The Library view gets a search field at the top. It does two jobs with one
input:

1. **Search** — filters the result list live by title and director (AND logic,
   FR-SF-01/02/03) and shows the match count (FR-SF-05).
2. **Add** — offers **"+ Add new film"** once the user has typed, below the
   films that already match.

   Originally this was an autocomplete panel listing the matches plus the add
   option. The panel was built and then removed: the filter applies on every
   keystroke, so the panel only repeated the titles already visible in the
   result list below it. The result list *is* the match list — so the add
   option belongs at its end (and is the only thing left when nothing
   matches). **Not yet built; this is the open design question of the add
   half.**

Adding a film therefore always happens *after* the user has seen every film
already in the library that matches the title. Duplicates are avoided by
construction rather than caught after the fact (FR-LIB-05).

The visible **"Add Film"** action (button on desktop, FAB on mobile) does not
open a form — it focuses the search field, so there is exactly one path into
the create flow. It stays visible because an add action that only appears once
you type is undiscoverable.

## Flow

```
Library view
  └─ search field (focused on arrival, and by the Add Film button)
       └─ result list, filtered live + match count
            ├─ matching existing films → Film Detail view
            └─ "+ Add new film"        → /films/new?title=<typed text>
```

## Work items

### 1. Library view — search (`views/library/`) — **partly done**

Built:

- [x] Search input at the top of the view.
- [x] Live filtering of the in-memory library (the whole list is already loaded
  via `FilmFacade.films`): case-insensitive substring match across **all** of a
  film's titles (FR-SF-01), AND-combined (FR-SF-03). The criteria live in
  `views/library/filters.ts` — a `LibraryCriteria` field plus one `PREDICATES`
  entry per dimension, which is the FR-EXT-05 seam.
- [x] Match count always visible (FR-SF-05).
- [x] Clear-all action (FR-SF-04).
- [x] The search field takes focus when the view is entered.
- [x] ~~`mat-autocomplete` panel listing the matching films' primary titles.~~
  Built, then removed — with live filtering the panel only echoed the result
  list beneath it.

Still open:

- [ ] Director as a second criterion (FR-SF-02) — one `PREDICATES` entry,
  no view change.
- [ ] "+ Add new film" at the end of the filtered result list, visually
  separated from the film rows; keyboard reachable. Deferred until
  `films/new` exists, since it would otherwise route nowhere.
- [ ] "Add Film" button / FAB focuses the search input.

### 2. Film form (`views/film-form/`, new)

Routed page at `films/new`, registered in `core/routes.registry.ts`. Reads
`?title=` and prefills the title field.

Fields:

| Field          | Required | Notes                                        |
| -------------- | -------- | -------------------------------------------- |
| Title          | yes      | prefilled from the search                    |
| Original title | no       | second title with `is_original` (see cut #1) |
| Release year   | yes      | 1888..current year                           |
| Director       | yes      |                                              |
| Runtime        | yes      | minutes, ≥ 1                                 |
| Genres         | yes      | ≥ 1, chips + autocomplete (FR-TAG-06)        |
| Tags           | yes      | ≥ 1, chips + autocomplete (FR-TAG-06)        |
| Poster URL     | no       | well-formed http(s) URL (FR-LIB-14)          |
| Watched on     | yes      | not in the future (FR-RAT-03)                |
| Rating         | no       | 0.5–5.0 in half steps, clearable → `null`    |

`is_favorite` and `delay_days` are not asked for — the system defaults them
(FR-LIB-02).

On submit: `POST /films` (film + first rating atomically, FR-LIB-03), then
navigate back to the Library, which reloads its list.

**Duplicate backstop.** The search makes a duplicate unlikely, not impossible —
the user can type a fresh title and then a year/director that collide. Handle
the `409 DUPLICATE_FILM` response by naming the colliding film and blocking the
create (FR-LIB-05). Creation can never be overridden into a duplicate.

### 3. Film data layer (`domain/film/`)

- `api.ts` — `create(dto)` as a plain `HttpClient.post` (`httpResource` is for
  reads only).
- `mapper.ts` — `toCreateDto`, the camelCase → snake_case direction.
- `facade.ts` — `create(input)`: maps, POSTs, reloads the library list.

### 4. Lookup data layer — **done**, as two modules

Landed as `domain/tag/` and `domain/genre/` rather than one `domain/lookup/`
module, behind the film-detail chip autocompletes. Both fetch once and filter
client-side; the `?prefix=` query parameter is unused, as planned.

## Backend

Nothing to do. `POST /films`, `GET /films`, `GET /tags` and `GET /genres` all
exist and are M1-complete.

`POST /films/duplicate-check` also exists but is **not used** by this design —
the search panel already shows the collision before the form opens. Keep the
endpoint; it is the natural fit if a live in-form probe is ever wanted.

## Deliberate cuts

1. **Two title slots, not n.** Primary title + one optional original title,
   instead of a general title list with primary radios. FR-LIB-01 permits
   several titles; the general list can arrive with the Edit view.
2. ~~**Film matches in the panel are display-only.**~~ Obsolete — the Film
   Detail view (§7.3) now exists. The panel's matches narrow the result list
   instead of navigating (the repo owner's call): the list rows are already
   the link into the detail view, so a second navigation path would be
   redundant.
3. **No offline write queue.** The create is a plain online POST. The DESIGN §7
   write queue belongs to its own milestone.

## Testing

- `library.spec.ts` — filtering narrows the list, the count matches, the add
  option is always present, the Add Film button focuses the input.
- `film-form.spec.ts` — required-field validation, `?title=` prefill, a valid
  form calls `FilmFacade.create`, a 409 blocks and names the colliding film.

## Estimate

~2 hours including tests.
