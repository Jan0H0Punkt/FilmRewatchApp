/**
 * The due-list cap (FR-RW-08, DESIGN §6.3) — a pure
 * formula, kept out of `RewatchFacade` because it needs `StatsFacade` and
 * `SettingsFacade` data the rewatch domain otherwise has no reason to read;
 * `views/rewatch/rewatch.ts` calls it directly (§6.1).
 */

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
 */
export function rewatchCap(share: number | null, watches: number, rewatches: number): number | null {
  if (share === null || share === 100) return null;
  const numerator = share * watches - 100 * rewatches;
  const denominator = 100 - share;
  return Math.max(0, Math.ceil(numerator / denominator));
}
