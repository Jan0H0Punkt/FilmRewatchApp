/** `StatsDto` → `Stats` (DESIGN §6.1). */
import type { StatsBlockDto, StatsDto } from './api';
import type { Stats, StatsBlock, TopName } from './model';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function toTopName(names: StatsBlockDto['top_genres']): TopName[] {
  return names.map((n) => ({
    name: n.name,
    watches: n.watches,
    averageRating: n.average_rating,
    score: n.score,
  }));
}

function toBlock(dto: StatsBlockDto, bucketLabel: (label: string) => string): StatsBlock {
  return {
    watches: dto.watches,
    firstWatches: dto.first_watches,
    rewatches: dto.rewatches,
    filmsReleasedThatYear: dto.films_released_that_year,
    distinctFilms: dto.distinct_films,
    minutesWatched: dto.minutes_watched,
    averageRating: dto.average_rating,
    ratingDistribution: dto.rating_distribution,
    topGenres: toTopName(dto.top_genres),
    topDirectors: toTopName(dto.top_directors),
    topTags: toTopName(dto.top_tags),
    topFilms: dto.top_films.map((f) => ({
      filmId: f.film_id,
      title: f.title,
      watches: f.watches,
      averageRating: f.average_rating,
      score: f.score,
    })),
    buckets: dto.buckets.map((b) => ({ label: bucketLabel(b.label), count: b.count })),
  };
}

export function toStats(dto: StatsDto): Stats {
  return {
    total: toBlock(dto.total, (year) => year),
    // A year block's buckets are months `"1"`…`"12"`.
    years: dto.years.map((y) => ({ year: y.year, ...toBlock(y, (month) => MONTHS[Number(month) - 1]) })),
  };
}
