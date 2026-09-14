# `core/` — cross-cutting infrastructure (DESIGN §4, §6.1)

This folder owns the client's cross-cutting infra. Built so far:

- `route-registry.ts` / `routes.registry.ts` — the §6.5 route registry
  (interface + the append-only entry list) that `app.routes.ts` projects into
  Angular `Routes` (FR-EXT-02); `navDestinations()` also drives the app shell's
  navigation.
- `clock.ts` — a shared, root-provided "now" for any view that displays a
  live-ish time.
- `theme.ts` — the light/dark/auto colour-scheme preference.

Still ahead: the HTTP client wiring and the cache-first + sync engine (§3.7,
§6.2 — `core/data` + `core/sync`), which arrive with M5.
