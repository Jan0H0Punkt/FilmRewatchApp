/** Settings domain model (DESIGN §6.1) — see docs/superpowers/specs/2026-09-25-rewatch-share-design.md. */

/** The one setting there is so far (FR-RW-08): `null` is Off, otherwise 0..100 in steps of 10. */
export interface Settings {
  readonly rewatchShare: number | null;
}
