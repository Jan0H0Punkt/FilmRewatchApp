/** `LetterboxdEntryDto` → `LetterboxdEntry` (DESIGN §6.1). */
import type { LetterboxdEntryDto } from './api';
import type { LetterboxdEntry } from './model';

export function toLetterboxdEntry(dto: LetterboxdEntryDto): LetterboxdEntry {
  return {
    id: dto.id,
    filmTitle: dto.film_title,
    filmYear: dto.film_year,
    filmUrl: dto.film_url,
    watchedDate: dto.watched_date,
    rating: dto.rating,
    rewatch: dto.rewatch,
    suggestedFilm: dto.suggested_film,
  };
}
