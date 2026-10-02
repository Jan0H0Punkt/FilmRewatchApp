/** Settings domain model (DESIGN §6.1) — see docs/superpowers/specs/2026-09-25-rewatch-share-design.md. */

/** The user's settings: the FR-RW-08 rewatch share and the FR-RW-09 watch pace. */
export interface Settings {
  /** `null` is Off, otherwise 0..100 in steps of 10. */
  readonly rewatchShare: number | null;
  /** Aim of one watch every N days (whole number ≥ 1); `null` is Off. */
  readonly watchIntervalDays: number | null;
}
