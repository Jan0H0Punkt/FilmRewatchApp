/** Statistics domain models (DESIGN §6.1) — see docs/superpowers/specs/2026-09-25-statistics-design.md. */
export interface TopName {
  readonly name: string;
  readonly watches: number;
  readonly averageRating: number;
  readonly score: number;
}

export interface TopFilm {
  readonly filmId: string;
  readonly title: string;
  readonly watches: number;
  readonly averageRating: number;
  readonly score: number;
}

export interface RatingCount {
  readonly value: number;
  readonly count: number;
}

/** A month (`Jan`…`Dec`) in a year block, a year in the all-time block. */
export interface Bucket {
  readonly label: string;
  readonly count: number;
}

export interface StatsBlock {
  readonly watches: number;
  readonly firstWatches: number;
  readonly rewatches: number;
  /** `null` in the all-time block, which has no single year. */
  readonly filmsReleasedThatYear: number | null;
  readonly distinctFilms: number;
  readonly minutesWatched: number;
  /** `null` when no watch in the block was rated (FR-RAT-12). */
  readonly averageRating: number | null;
  readonly ratingDistribution: readonly RatingCount[];
  readonly topGenres: readonly TopName[];
  readonly topDirectors: readonly TopName[];
  readonly topTags: readonly TopName[];
  readonly topFilms: readonly TopFilm[];
  readonly buckets: readonly Bucket[];
}

export interface YearStats extends StatsBlock {
  readonly year: number;
}

export interface Stats {
  readonly total: StatsBlock;
  /** Newest year first, empty years included. */
  readonly years: readonly YearStats[];
}
