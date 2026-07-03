# `views/` — the three screens (DESIGN §4, §6.5)

Intentional **M0 stub** (PR7). The presentation layer: three routed views —
`rewatch/`, `library/` (Search & Filter + Add Film), `film-detail/` — each
composing domain facades into per-view ViewModels (§6.1). Views call facades
**only**, never the data layer, and hold no rules.

Real screens and the adaptive navigation (drawer/bottom bar, §6.5) arrive in
**M3**. New views register in `core/route-registry.ts` (FR-EXT-02).
