# Open Decisions

**Version:** 1.0  
**Status:** Living  
**Created:** 2026-06-05  
**Last updated:** 2026-06-05  
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

---

## M4 — Rewatch engine

- **[impl] Scheduler mechanism (daily rewatch job)** — a container/cron entry beside the backend, vs. an
  in-process scheduler started with the app. (DESIGN §5.8, §8.1.)
- **[design] Rewatch algorithm internals** — the user supplies the scoring logic; only the input/output contract
  is fixed. (DESIGN §5.8.)

---

## M5 — Cache & PWA

- **[impl] Angular IndexedDB wrapper** — a thin typed helper vs. a library (e.g. Dexie) for the cache + sync store.
  (DESIGN §6.2.)

---

## Post-release (not milestone-bound)

- **[design] Performance targets** — none set until real usage is observable. (DESIGN §8.)
