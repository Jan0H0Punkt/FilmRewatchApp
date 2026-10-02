# `domain/settings/`

Data access and business logic for the one-row settings singleton
(`GET`/`PUT /settings`, FR-RW-08/09) — the rewatch share and the watch pace the
Settings view edits and the Rewatch view's §Cap formula reads. `pace.ts` holds
the pure pace rule (expected watches, snackbar text).

`facade.ts` applies a save optimistically and rolls it back on failure,
mirroring `FilmFacade.update`; the Settings view's `mat-select` is bound
straight to `rewatchShare`, so the rollback is also what re-selects the
previous option — the view has no revert logic of its own.
