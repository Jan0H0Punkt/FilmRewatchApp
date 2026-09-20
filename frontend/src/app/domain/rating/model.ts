/**
 * Rating write-direction domain models (DESIGN §6.1, phase 2 of
 * `open work/library-view/film-detail-view.md`).
 *
 * The read model for one rating event, `RatingHistoryEntry`, already lives in
 * `domain/film/model.ts` — the film detail projection is the only place
 * ratings are read from (REQ §7.3 Section B), so it is reused here rather
 * than declared a second time.
 */

/**
 * The stand-in `watchDate` for "I have seen this before, I don't know when"
 * (FR-RAT-04/12), mirroring the backend's `EARLIER_WATCH_DATE`.
 *
 * Such a watch still has to count — the rewatch engine's `watch_count` is the
 * number of rating entries — but it must never look like the *most recent*
 * one, which is `MAX(watch_date)`. 1888, the year of the first film ever made,
 * sits below every real watch date, so a prior watch adds its step without
 * ever moving the anchor the next rewatch is measured from.
 */
export const EARLIER_WATCH_DATE = '1888-01-01';

/** The `POST /films/{id}/ratings` payload (FR-RAT-01..04). */
export interface RatingDraft {
  /** `null` for a watch the user explicitly chose not to rate (FR-RAT-12). */
  readonly value: number | null;
  /** ISO `yyyy-MM-dd`, never in the future (FR-RAT-03). */
  readonly watchDate: string;
}

/**
 * The `DELETE /ratings/{id}` outcome (FR-RAT-07). Deleting a film's last
 * rating deletes the film with it; `filmDeleted` tells the two outcomes
 * apart so the view knows whether to stay or navigate to the Library.
 */
export interface RatingDeletionResult {
  readonly ratingId: string;
  readonly filmId: string;
  readonly filmDeleted: boolean;
}
