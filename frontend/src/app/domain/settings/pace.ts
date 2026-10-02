/**
 * The FR-RW-09 watch-pace rule — pure, so the Rewatch cap and the film-detail
 * snackbar share one definition of "where should I be by today".
 */

const MS_PER_DAY = 86_400_000;

/** 1 January is day 1. Via `Date.UTC` differences so a DST change cannot shift the count. */
function dayOfYear(today: Date): number {
  const start = Date.UTC(today.getFullYear(), 0, 1);
  return Math.round((Date.UTC(today.getFullYear(), today.getMonth(), today.getDate()) - start) / MS_PER_DAY) + 1;
}

/** Watches a one-film-every-`intervalDays` pace calls for by the end of `today`. */
export function expectedWatches(intervalDays: number, today: Date): number {
  return Math.floor(dayOfYear(today) / intervalDays);
}

/** The snackbar line: how far `watchesThisYear` is from the pace, `diff` = actual - expected. */
export function paceMessage(intervalDays: number, watchesThisYear: number, today: Date): string {
  const expected = expectedWatches(intervalDays, today);
  const diff = watchesThisYear - expected;
  const films = (n: number): string => `${n} film${n === 1 ? '' : 's'}`;
  if (diff === 0) return `On pace · ${films(watchesThisYear)} this year`;
  const direction = diff < 0 ? 'behind' : 'ahead of';
  return `${films(Math.abs(diff))} ${direction} pace (${watchesThisYear} of ${expected})`;
}
