/**
 * The canonical film domain model (DESIGN §6.1) — shared by every view.
 *
 * Only the fields a screen actually renders live here; the wire projection
 * carries more (rating history, timestamps, `delay_days`), which the Film
 * Detail and Rewatch views add when they need them.
 */
export interface Film {
  readonly id: string;
  /** The film's primary title (REQ §4.1) — the one every list shows. */
  readonly primaryTitle: string;
  readonly releaseYear: number;
  readonly director: string;
  readonly runtimeMinutes: number;
  readonly genres: readonly string[];
  readonly tags: readonly string[];
  readonly posterImage: string | null;
  /**
   * Computed server-side on every read, never stored (FR-RAT-09/10).
   * `null` when every watch of the film was left unrated (FR-RAT-11/12) —
   * distinct from a rating of zero, which cannot exist. Rendered as the
   * FR-RAT-13 placeholder, never as an empty star row.
   */
  readonly averageRating: number | null;
  readonly isFavorite: boolean;
}
