# Open Decisions

**Version:** 1.0  
**Status:** Living  
**Created:** 2026-06-05  
**Last updated:** 2026-09-14  
**Companion to:** [DESIGN_V1.md](../designs/DESIGN_V1.md) · [FUTURE_WORK_V1.md](./FUTURE_WORK_V1.md)  

Open **design** decisions — choices not yet made in DESIGN_V1.md — **ordered by the milestone** at which each is
due. Each is tagged:

- **[impl]** — an implementation choice.
- **[design]** — a design point the requirements deliberately left open.

(Milestones with no open decisions are omitted.)

---

## M3 — Angular shell

- **[design] Search/filter UX** — concrete controls/layout and live-vs-debounced-vs-submit behaviour.
  (DESIGN §7.2.)
- **[design] Responsive breakpoints & minimum touch-target size** (touch-target refined in the M7 a11y pass).
  (DESIGN §7.4.)
  **Partially decided (2026-09-14):** the navigation switches between the
  bottom bar and the sidebar at `900px`. The rest of the responsive pass is
  still open.

---

## M4 — Rewatch engine

- **[impl] Scheduler mechanism (daily rewatch job)** — **Decided (2026-09-14):**
  an in-process `asyncio` task owned by the FastAPI lifespan
  (`app/rewatch/scheduler.py`). The deployment target is a single laptop
  running one container (§1.3), where a scheduler that lives and dies with the
  app is the whole requirement — and every start recomputes, so a restart costs
  nothing. (DESIGN §5.8, §8.1.)
- **[design] Rewatch algorithm internals** — **Decided (2026-09-14):** the
  repo owner's formula, in `algorithm.interval_days`. A film waits a
  rating-derived floor plus a spacing of `(watch_count + reverse_rating) *
  (10 * reverse_rating + runtime_minutes)`, where `reverse_rating` is the
  average rating doubled onto a 1..10 scale and subtracted from 10. The rating
  therefore drives the interval quadratically; each prior watch adds one step;
  a longer film widens every step. **Revised 2026-09-19:** the floor is keyed on
  the rating rather than shared — one year per full star counted down from six,
  so five stars floor at one year and one star at five, with a half step
  rounding up to the full star above it (4.5 counts as 5) and an unrated film
  floored at six. Favourites halve the finished interval, floor included,
  rounded up, which is the **one case that falls inside the year its rating
  bought** — a five-star favourite can come due in six months. The result is
  unbounded
  above (**revised 2026-09-19:** `MAX_INTERVAL_DAYS` removed — a ceiling
  collapsed the bottom of the rating scale onto a single due date, and measured
  against the real library it never bound anything else). `delay_days` is added
  on top of the scored interval, because a deferral is the user's instruction
  rather than something the scoring invented.
  Scoring is a pure function of the input row — no clock, no randomness — so a
  film cannot be due one run and gone the next. FR-RW-02 gained
  `runtime_minutes`; the output contract is unchanged. (DESIGN §5.8.)

---

## M5 — Cache & PWA

- **[impl] Angular IndexedDB wrapper** — a thin typed helper vs. a library (e.g. Dexie) for the cache + sync store.
  (DESIGN §6.2.)

---

## Post-release (not milestone-bound)

- **[design] Performance targets** — none set until real usage is observable. (DESIGN §8.)
