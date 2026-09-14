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
- **[design] Rewatch algorithm internals** — **Still open.** The repo owner
  supplies the scoring logic. A documented placeholder ships in its place
  (`app/rewatch/algorithm.py`): every film is due one year after its last
  watch, deferred by `delay_days`; `average_rating`, `watch_count` and
  `is_favorite` are accepted and ignored. The input/output contract is fixed,
  so the real algorithm replaces `suggest`'s body and nothing else.
  (DESIGN §5.8.)

---

## M5 — Cache & PWA

- **[impl] Angular IndexedDB wrapper** — a thin typed helper vs. a library (e.g. Dexie) for the cache + sync store.
  (DESIGN §6.2.)

---

## Post-release (not milestone-bound)

- **[design] Performance targets** — none set until real usage is observable. (DESIGN §8.)
