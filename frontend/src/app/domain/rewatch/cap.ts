/**
 * The §Cap due-list cap (FR-RW-08,
 * docs/superpowers/specs/2026-09-25-rewatch-share-design.md) — a pure
 * formula, kept out of `RewatchFacade` because it needs `StatsFacade` and
 * `SettingsFacade` data the rewatch domain otherwise has no reason to read;
 * `views/rewatch/rewatch.ts` calls it directly (§6.1).
 */

import { expectedWatches } from '../settings/pace';

/**
 * The fewest additional rewatches still needed for `rewatches / watches` to
 * reach `share`. `null` means no cap: `share` is `null` (Off) or `100` (the
 * formula would divide by zero, and "only rewatches" puts every due film back
 * in play anyway).
 *
 * Computed as integers throughout (`share * watches - 100 * rewatches`, over
 * `100 - share`), not `share / 100`: that fraction is often inexact in
 * floating point (`0.3` chief among them), and multiplying it back out can
 * round `Math.ceil` up to one more than the true answer — 30 % of 10 watches
 * with 3 rewatches already banked must read `k = 0`, not `1`.
 *
 * With a watch pace set (FR-RW-09, `intervalDays`) the target is measured
 * against the watches the pace calls for by `today`, `E`, instead of the
 * watches actually logged: the cap is `ceil(E * share / 100 - rewatches)`,
 * floored at 0 — again in integers, `ceil((E * share - 100 * rewatches) / 100)`.
 */
export function rewatchCap(
  share: number | null,
  watches: number,
  rewatches: number,
  intervalDays: number | null = null,
  today: Date = new Date(),
): number | null {
  if (share === null || share === 100) return null;
  if (intervalDays !== null) {
    const expected = expectedWatches(intervalDays, today);
    return Math.max(0, Math.ceil((expected * share - 100 * rewatches) / 100));
  }
  const numerator = share * watches - 100 * rewatches;
  const denominator = 100 - share;
  return Math.max(0, Math.ceil(numerator / denominator));
}
