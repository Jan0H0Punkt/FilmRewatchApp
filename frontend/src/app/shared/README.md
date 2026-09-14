# `shared/` — reusable dumb UI components & display pipes (DESIGN §4, §6.5)

Reusable presentational pieces shared across views (FR-EXT-03), each meeting
WCAG 2.1 AA (NFR-A11Y-01..04). They hold no data and perform no write: state
and persistence stay with the calling view and its facades (§6.1).

- `confirm-dialog/` — the confirmation step before a destructive action (FR-LIB-11, FR-RAT-07).
- `editable-chips/` — a chip row with in-place editing and autocomplete; the
  film detail view's tags and genres (FR-TAG-03/06, REQ §4.4).
- `rating-stars.ts` — the app's one star-rendering rule (FR-RAT-09/11/13),
  shared by the Library and Rewatch views.

A film card and poster-with-placeholder are still unbuilt — views hold those
inline until a second caller appears.
