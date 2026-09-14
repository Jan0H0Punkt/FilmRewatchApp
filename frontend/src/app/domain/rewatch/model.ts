/** The rewatch domain model and the §7.1 card ViewModel (DESIGN §6.1). */

/** One entry of the due-list, as the algorithm ordered it (FR-RW-03). */
export interface RewatchSuggestion {
  readonly filmId: string;
  /** `0` is due today; negative is overdue by that many days. Never positive. */
  readonly daysUntilNextRewatch: number;
}

/**
 * One card of the §7.1 grid — a suggestion joined to its film. Display-ready:
 * the view prints these fields and computes nothing.
 */
export interface RewatchCardVm {
  readonly id: string;
  readonly title: string;
  readonly year: number;
  readonly posterImage: string | null;
  /** Five Material star icon names, or `null` for an unrated film (FR-RAT-13). */
  readonly ratingStars: readonly string[] | null;
  readonly ratingLabel: string;
  readonly isFavorite: boolean;
  /** "Due now" or "Overdue by N days" (§7.1 Rewatch status). */
  readonly dueLabel: string;
}
