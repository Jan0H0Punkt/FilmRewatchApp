/**
 * The canonical film domain model (DESIGN §6.1) — shared by every view.
 *
 * `Film` carries only what the library list renders; `FilmDetail` below adds
 * the rest of the §7.3 wire projection (rating history, timestamps,
 * `delay_days`) for the Film Detail and Rewatch views.
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
   * Derived client-side from `ratingHistory` on every read, never sent by the
   * API and never stored (FR-RAT-09/10, DESIGN §7.3). `null` when every watch
   * of the film was left unrated (FR-RAT-11/12) — distinct from a rating of
   * zero, which cannot exist. Rendered as the FR-RAT-13 placeholder, never as
   * an empty star row.
   */
  readonly averageRating: number | null;
  readonly isFavorite: boolean;
}

/** One title of a film (REQ §4.1 Title object) — the detail view lists all of them. */
export interface FilmTitle {
  readonly value: string;
  readonly isPrimary: boolean;
  readonly isOriginal: boolean;
}

/** One rating event (REQ §4.2, §7.3 Section B). `domain/rating/` (phase 2) owns writing these. */
export interface RatingHistoryEntry {
  readonly id: string;
  /** `null` for a watch the user chose not to rate (FR-RAT-12). */
  readonly value: number | null;
  readonly watchDate: string;
  readonly createdAt: string;
}

/**
 * The full §7.3 detail projection (`GET /films/{id}`) — everything the
 * library list omits: every title, the rewatch delay, the rating history,
 * and the record timestamps.
 */
export interface FilmDetail extends Film {
  readonly titles: readonly FilmTitle[];
  readonly delayDays: number;
  /** Newest first (FR-RAT-05/06), as the backend orders it. */
  readonly ratingHistory: readonly RatingHistoryEntry[];
  readonly createdAt: string;
  readonly updatedAt: string;
}

/**
 * The `PATCH /films/{id}` payload, write direction (FR-LIB-06). Every field
 * optional; the caller sets exactly one at a time (phase 3: `isFavorite` or
 * `delayDays`) so the DTO mapper sends only what changed.
 */
export interface FilmPatch {
  readonly isFavorite?: boolean;
  readonly delayDays?: number;
}
