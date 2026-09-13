/**
 * Rating write-direction domain models (DESIGN §6.1, phase 2 of
 * `open work/library-view/film-detail-view.md`).
 *
 * The read model for one rating event, `RatingHistoryEntry`, already lives in
 * `domain/film/model.ts` — the film detail projection is the only place
 * ratings are read from (REQ §7.3 Section B), so it is reused here rather
 * than declared a second time.
 */

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
