# Rewatch share — design

Date: 2026-09-25 · Status: approved in chat, pending spec review

## Goal

A setting for the share of this year's watches that should be rewatches. The Rewatch view caps its due list so that
it offers only as many films as it takes to reach that share; once you are on or over the target, it shows none.

## Setting

- **Rewatch share:** `null` (Off, the default) or an integer percentage `0..100` in steps of 10.
- Off means the Rewatch view behaves exactly as today — no cap, no note.
- Stored in the backend so laptop and phone share one value (single user, REQ §2).

## Cap

Inputs, all for the **current calendar year** — the browser's year, picked the way the Statistics view picks it:

- `W` — watches this year, `R` — rewatches this year: the current year's `watches` and `rewatches` from
  `GET /api/v1/stats` (`StatsBlock`). Reusing them keeps one definition of "first watch" (the film's earliest dated
  entry; undated entries are not counted in any year). No year block for the current year means `W = R = 0`.
- `t` — the share as a fraction (`rewatch_share / 100`).

The visible count is `k = max(0, ceil((t·W − R) / (1 − t)))`: the rewatches needed for `R / W` to reach `t`.

| Case | Result |
| --- | --- |
| Share Off | No cap. |
| `t = 1` (100%) | No cap — the formula divides by zero, and "only rewatches" means every due film is fair game. |
| `t = 0` | `k = 0`, list empty. |
| `W = 0` (e.g. 1 January) | `k = 0`, list empty until the first watch of the year. Consistent with the rule; accepted. |
| Stats fail to load | No cap — failing open shows the full list rather than an unexplained empty one. |

The view shows the **first `k`** entries of the due list. FR-RW-04 forbids re-sorting but allows filtering to a subset;
taking a prefix keeps the most-overdue-first order.

When the cap hides at least one film, a single line sits above the list: "Showing k of n due films · t% rewatch target".
With `k = 0` the line is the whole content (`Showing 0 of n …`), replacing the normal empty state so an empty list is
explained. When nothing is hidden (`k ≥ n`), no line.

## Backend — `backend/app/settings/`

A feature module in the usual layers (`models`, `repository`, `service`, `schemas`, `router`, `dependencies`), like
`tags/`.

- **Table `settings`:** exactly one row — `id` integer primary key fixed to `1` with a `CHECK (id = 1)`,
  `rewatch_share` integer nullable with `CHECK (rewatch_share BETWEEN 0 AND 100 AND rewatch_share % 10 = 0)`,
  `updated_at`. Migration `0009_settings.py` creates the table and inserts the row with `rewatch_share = NULL`.
- **`GET /api/v1/settings`** → `{ "rewatch_share": int | null }`.
- **`PUT /api/v1/settings`** with the same body replaces it and returns the stored state. Pydantic validates the range
  and step (422 otherwise); the DB constraint is the backstop.
- The rewatch algorithm and its daily projection are untouched — the cap is a view concern.

## Frontend

- **`domain/settings/`** — `model.ts`, `mapper.ts`, `api.ts`, `facade.ts` per §6.1. The facade exposes the share as a
  signal and a `setRewatchShare(value)` write.
- **Settings view** — replaces "Nothing is configurable yet." with a `mat-slider` labelled "Rewatch share", 0% to 100%
  in steps of 10, "New watches" at the 0 end and "Rewatches" at the 100 end. A stored Off (`null`) shows as 100% — both
  mean no cap. Saves on release; a failed save shows the facade's error and keeps the previous value.
- **Rewatch view** — reads `SettingsFacade` and `StatsFacade` (both facades, per §6.1); the formula lives in a pure
  function `rewatchCap(share, watches, rewatches): number | null` (`null` = no cap) in the rewatch domain, unit-tested
  on every row of the table above.

## Docs

- REQUIREMENTS §5.5: new **FR-RW-08** — the rewatch-share setting and the cap. §7.1: the cap note.
- DESIGN §5.3: the two `/settings` routes. §7.1 (views): the cap as a permitted FR-RW-04 subset filter.
- `docs/requirements/FUTURE_WORK_V1.md` is unchanged — the global tag/genre delete still waits for its own work, but now
  has a Settings page to land on.

## Testing

- Backend: service unit tests against a fake repository; router tests for GET, PUT, and 422 on `55` / `110` / `-10`.
- Frontend: `rewatchCap` table test; Settings view saves on change; Rewatch view shows the prefix and the note.
- Gate: pyright strict + pytest on the backend, `npm run build`, `npm test`, `npm run lint` on the frontend.

## Out of scope

- A pace line when the share is Off, or any display in Statistics.
- A configurable window — it is always the current year.
- Changing the backend rewatch algorithm.
