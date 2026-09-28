/** Letterboxd review-list domain model (DESIGN §6.1, REQ §5.7). */

/** The film the sync matched (FR-LBX-04), by its primary title. */
export interface SuggestedFilm {
  readonly id: string;
  readonly title: string;
}

/** One open Letterboxd diary entry awaiting review. */
export interface LetterboxdEntry {
  readonly id: string;
  readonly filmTitle: string;
  readonly filmYear: number;
  readonly filmUrl: string;
  /** `yyyy-MM-dd`, as on the wire. */
  readonly watchedDate: string;
  /** `null` = logged without a rating (FR-LBX-08). */
  readonly rating: number | null;
  readonly rewatch: boolean;
  readonly suggestedFilm: SuggestedFilm | null;
}
