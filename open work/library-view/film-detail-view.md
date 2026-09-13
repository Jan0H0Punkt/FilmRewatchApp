# Film Detail view

Status: **phases 1–3 implemented** (2026-09-13), phase 4 deferred. Target
milestone: M3 (§7.3). The repo is in M1 — this is deliberately ahead of the
milestone sequence.

Phase 4 (Edit) waits for `add-film-via-search.md`, which builds the
`views/film-form/` it reuses — writing an edit-only form first would duplicate
the same ten fields. Until then the detail view has no Edit control; everything
else in §7.3 works.

Requirements covered: FR-LIB-06..16, FR-RAT-01..08, FR-RAT-12/13, FR-TAG-03/06.
Design references: REQUIREMENTS §7.3, §4.1, §4.2; DESIGN §6.1, §6.5.

Sibling plan: `add-film-via-search.md`. Phase 1 below closes that plan's
deliberate cut #2 (library matches become navigable); phase 4 reuses the film
form it introduces. Phases 1–3 do **not** depend on it and can land first.

## The idea

`film/:id` is the one screen that shows everything the backend stores about a
film and the only place it can be changed. The backend is **already complete**
for all of it — `GET/PATCH/DELETE /films/{id}`, `POST /films/{id}/ratings`,
`DELETE /ratings/{id}` are M1-done. Every phase below is frontend-only.

The view splits exactly as §7.3 does:

```
film/:id
  ├─ Section A — metadata
  │    ├─ poster · titles · year · director · runtime · genres · tags
  │    ├─ average rating (read-only, FR-RAT-09/13)
  │    ├─ favourite toggle + rewatch delay   → PATCH /films/{id}
  │    ├─ Edit   → films/:id/edit (the add-film form in edit mode)
  │    └─ Delete → confirm (FR-LIB-11) → DELETE, back to Library
  └─ Section B — rating history, newest first
       ├─ Add rating   → POST /films/{id}/ratings
       └─ per entry: Delete → confirm → DELETE /ratings/{id}
            └─ `film_deleted: true` → navigate back to the Library
```

The two write paths that can make the current film vanish — deleting the film,
and deleting its last rating — both end on the Library route. Nothing else
navigates away.

## Navigation

**In.** Three entry points, one of which exists today:

| From                                                            | Phase              |
| --------------------------------------------------------------- | ------------------ |
| Library row card — the whole card is the link                   | 1                  |
| Add-film autocomplete match ("open that film instead", FR-LIB-05) | add-film's cut #2 |
| Rewatch view (§7.1)                                             | not built          |

**Out.** The view draws its **own back control** — `arrow_back` icon button,
`routerLink="/library"`, at the top of Section A. Not optional: the app shell
is still a title plus the theme toggle (the §6.5 drawer / bottom bar arrives
later in M3), and an installed PWA has no browser back button, so without this
the detail view is a dead end. Remove it when the adaptive navigation lands.

The two deletes (film, last rating) are the other exits, both to the Library.

## Phases

Each phase is shippable on its own, in order.

### 1. Read-only detail view

**Done.**

**Data layer (`domain/film/`).**

- `api.ts` — `detail`, a second `httpResource` keyed on a `selectedId` signal:
  the URL factory returns `undefined` while the id is `null`, so the request
  only fires once a film is selected. Same loading/error signals the list
  already exposes (REQ §7.2).
- `model.ts` — `FilmDetail extends Film` with the fields the list does not
  carry: `titles` (all of them, with `isPrimary`/`isOriginal`), `delayDays`,
  `ratingHistory`, `createdAt`, `updatedAt`. The `model.ts` docstring already
  promises exactly this.
- `mapper.ts` — `toFilmDetail`, alongside the existing `toFilm`.
- `facade.ts` — `select(id)`, `detail`, `detailIsLoading`, `detailError`,
  `reloadDetail()`.

**View (`views/film-detail/`).** Registered in `core/routes.registry.ts` as
`film/:id` — the interface's own example path. Add `withComponentInputBinding()`
to `app.config.ts` (one line) so the component takes `id = input.required<string>()`
instead of poking at `ActivatedRoute`.

The ViewModel shaping lives in the component, as in `library.ts`. Reuse its
`ratingStars()` helper for the large average-rating display — move it to
`shared/` when the second copy would otherwise appear, not before.

Poster: large, with the FR-LIB-16 neutral placeholder — the same
`film__poster--empty` mat-icon block the library row uses.

**Library becomes navigable.** Wrap each `library.html` row card in a
`routerLink` to `/film/{{ row.id }}`. That is the whole change on that side.

### 2. Rating history actions (Section B)

**Done.**

**`domain/rating/` (new).** `model.ts` (`RatingEntry`), `mapper.ts`, `api.ts`
(`add(filmId, dto)` → `POST /films/{id}/ratings`, `remove(ratingId)` →
`DELETE /ratings/{id}`; plain `HttpClient` calls — `httpResource` is reads
only), `facade.ts`.

`RatingFacade` injects `FilmFacade` and reloads the detail itself after a
write, so the view makes one call, not two. This mirrors the backend, where
the ratings router deliberately depends on `FilmService` for the same reason.

**Add Rating.** Inline form: star picker 0.5–5.0 in half steps, an explicit
**"Don't rate this"** choice that sends `value: null` (FR-RAT-12 — a missing
score must be stated, never inferred), and a `watch_date` picker with `max` =
today (FR-RAT-03). A future date still comes back as `FUTURE_WATCH_DATE`;
surface the envelope's `message`.

**Delete entry.** Confirmation (FR-RAT-07), then branch on the response's
`film_deleted`: `false` → reload the detail; `true` → navigate to the Library.

**Confirmation dialog (`shared/confirm-dialog/`, new).** One small `MatDialog`
component taking a title, a message and a confirm label — two call sites
already (film delete, rating delete), so it earns its file on the first use.

### 3. Film-level actions (Section A)

**Done.**

- **Favourite toggle** and **rewatch delay** — inline, each a
  `PATCH /films/{id}` with the single changed field (FR-LIB-06). `FilmFacade.update(id, patch)`.
- **Delete Film** — the shared confirm dialog (FR-LIB-11), then
  `DELETE /films/{id}`, then back to the Library, which reloads.

### 4. Edit form

**Deferred** — see the status note at the top.

`films/:id/edit` routes to the **same** `views/film-form/` component the
add-film plan introduces, in edit mode: prefilled from the detail, submitting
`PATCH` instead of `POST`. A separate edit form would be the same ten fields
twice.

Only the user-editable fields appear (titles, year, director, runtime, genres,
tags, poster, `is_favorite`, `delay_days`). `average_rating`, `created_at` and
`updated_at` are display-only in Section A and are not in the form — the
backend rejects them as unknown fields anyway.

Handle `409 DUPLICATE_FILM` the way the create does: name the colliding film,
block the save, leave the edit unapplied (FR-LIB-09).

## UI components

**Angular Material M3 throughout.** Before building any element here, check
whether `@angular/material` already ships it and use that; hand-rolled markup
is the exception and needs a reason. Theming goes through the single
`mat.theme(...)` include in `styles.scss` — per-element tweaks use
`var(--mat-sys-*)` / `mat.<component>-overrides((...))`, and any density or
colour mixin gets a real `mat.define-theme((...))` map, never a bare number
(see `frontend/CLAUDE.md`, "Material theming").

| Element                        | Component                                      |
| ------------------------------ | ---------------------------------------------- |
| Section A / B containers       | `mat-card` (+ `mat-divider`)                    |
| Back, Edit, Delete, Add Rating | `matIconButton` / `matButton`                   |
| Genres, tags                   | `mat-chip-set` / `mat-chip` (as in `library.html`) |
| Favourite toggle               | `matIconButton` + `favorite` / `favorite_border` |
| Rewatch delay                  | `mat-form-field` + `matInput type="number"`     |
| Rating history list            | `mat-list` / `mat-list-item`                    |
| `watch_date` picker            | `matDatepicker` with `[max]="today"` (FR-RAT-03) |
| Confirmation dialogs           | `MatDialog`                                     |
| Poster placeholder             | `mat-icon` (FR-LIB-16)                          |

**A heart, not a star.** The favourite control is a heart icon button
(`favorite` filled / `favorite_border` outlined), with `aria-pressed` carrying
the state. A star would collide with the rating stars sitting next to it —
which is exactly what `library.html` does today, printing `star` for
`is_favorite` a few pixels from the five rating stars. Phase 1 already touches
that file for the `routerLink`; swap its icon to `favorite` in the same edit so
both screens say the same thing.

`matDatepicker` needs `provideNativeDateAdapter()` in `app.config.ts` — one
line, and the only new provider this plan adds besides
`withComponentInputBinding()`.

**The two exceptions.** Material has no star-rating component, so both the
large read-only average (Section A) and the 0.5–5.0 picker (Section B) are
composed from `mat-icon` / `matIconButton` — the same approach `library.ts`
already takes with `ratingStars()`. Everything else on this screen is stock
Material; if a new element tempts a custom widget, look for the Material one
first.

## Deliberate cuts

1. **No tag add/remove directly on the detail view.** §7.3 offers it; the Edit
   form covers the same ground with one input surface instead of two. Revisit
   if tagging turns out to be the frequent operation.
2. **`ratingStars()` stays duplicated** between library and detail until a
   third caller appears. Two copies of eight lines are cheaper than a shared
   component with a props contract.
3. **No optimistic updates.** Every write reloads the detail. The backend is on
   the same laptop; the round trip is not worth a rollback path.
4. **No offline write queue** — same reason as the add-film plan: DESIGN §7's
   queue is its own milestone.

## Testing

- `film-detail.spec.ts` — loading/error/loaded states; the average renders as
  a dash when `averageRating` is `null` (FR-RAT-13); history is newest-first;
  `film_deleted: true` navigates to the Library; the delete confirm is required
  before the facade is called.
- `rating-facade.spec.ts` — an unrated entry sends `value: null`, not an
  omitted key.
- `library.spec.ts` — the row links to `/film/:id`.

## Estimate

- Phase 1: ~1 h · Phase 2: ~1 h · Phase 3: ~30 min · Phase 4: ~45 min
- ~3 h 15 total, including tests.
