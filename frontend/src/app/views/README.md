# `views/` — the screens (DESIGN §4, §6.5)

The presentation layer: the three primary views — `rewatch/`, `library/`
(Search & Filter), `film-detail/` — plus `film-form/`, which serves both
`films/new` and `film/:id/edit`, and `settings/`, an empty shell so far. Each
composes domain facades into per-view ViewModels (§6.1). Views call facades
**only**, never the data layer, and hold no rules.

The adaptive navigation (bottom bar/sidebar, §6.5) is built in `app.ts` and
`app.html`, driven by the destinations each view registers. New views register
in `core/routes.registry.ts` (FR-EXT-02).
