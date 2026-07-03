# `core/` — cross-cutting infrastructure (DESIGN §4, §6.1)

Intentional **M0 stub** (PR7). This folder owns the client's cross-cutting
infra: the HTTP client wiring, the cache-first + sync engine (§3.7, §6.2 —
`core/data` + `core/sync`), config, and error handling. All of that arrives
in **M3+**; adding it earlier would violate the milestone's out-of-scope list.

Already here in M0: `route-registry.ts` — the §6.5 route registry stub that
`app.routes.ts` projects into Angular `Routes` (FR-EXT-02).
