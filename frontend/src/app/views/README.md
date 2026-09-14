# `views/` — the three screens (DESIGN §4, §6.5)

The presentation layer: three routed views — `rewatch/`, `library/` (Search &
Filter; Add Film is not built yet), `film-detail/` — each composing domain
facades into per-view ViewModels (§6.1). Views call facades **only**, never
the data layer, and hold no rules.

The adaptive navigation (bottom bar/sidebar, §6.5) is built in `app.ts` and
`app.html`, driven by the destinations each view registers. New views register
in `core/routes.registry.ts` (FR-EXT-02).
