/** Domain ↔ DTO mapping for ratings (DESIGN §6.1). Write direction: domain → DTO. */
import type { RatingCreateDto, RatingDeletionResultDto } from './api';
import type { RatingDeletionResult, RatingDraft } from './model';

/** Maps an add-rating draft to the wire payload — `value` stays explicit, even when `null` (FR-RAT-12). */
export function toRatingCreateDto(draft: RatingDraft): RatingCreateDto {
  return { value: draft.value, watch_date: draft.watchDate };
}

/** Maps the delete-rating response back to the domain shape. */
export function toRatingDeletionResult(dto: RatingDeletionResultDto): RatingDeletionResult {
  return { ratingId: dto.rating_id, filmId: dto.film_id, filmDeleted: dto.film_deleted };
}
