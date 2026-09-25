# `domain/settings/`

Data access and business logic for the one-row settings singleton
(`GET`/`PUT /settings`, FR-RW-08) — so far just the rewatch-share setting the
Settings view edits and the Rewatch view's §Cap formula reads.

`facade.ts` applies a save optimistically and rolls it back on failure,
mirroring `FilmFacade.update`; the Settings view's `mat-select` is bound
straight to `rewatchShare`, so the rollback is also what re-selects the
previous option — the view has no revert logic of its own.
