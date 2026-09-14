/** DTO → domain → ViewModel mapping for rewatch suggestions (DESIGN §6.1). */
import { ratingLabelFor, ratingStarsFor } from '../../shared/rating-stars';
import type { Film } from '../film/model';
import type { RewatchSuggestionDto } from './api';
import type { RewatchCardVm, RewatchSuggestion } from './model';

export function toRewatchSuggestion(dto: RewatchSuggestionDto): RewatchSuggestion {
  return { filmId: dto.film_id, daysUntilNextRewatch: dto.days_until_next_rewatch };
}

/** The §7.1 "Rewatch status" wording. Only `<= 0` can reach here (FR-RW-03). */
export function dueLabelFor(daysUntilNextRewatch: number): string {
  if (daysUntilNextRewatch >= 0) return 'Due now';
  const days = -daysUntilNextRewatch;
  return `Overdue by ${days} day${days === 1 ? '' : 's'}`;
}

/** Joins a suggestion to its film to produce one card (§6.3). */
export function toRewatchCardVm(film: Film, suggestion: RewatchSuggestion): RewatchCardVm {
  return {
    id: film.id,
    title: film.primaryTitle,
    year: film.releaseYear,
    posterImage: film.posterImage,
    ratingStars: ratingStarsFor(film.averageRating),
    ratingLabel: ratingLabelFor(film.averageRating),
    isFavorite: film.isFavorite,
    dueLabel: dueLabelFor(suggestion.daysUntilNextRewatch),
  };
}
