/** DTO → domain mapping for films (DESIGN §6.1, read direction). */
import type { FilmDto } from './api';
import type { Film } from './model';

/**
 * The backend guarantees exactly one primary title per film (the §5.2 partial
 * unique index) and orders titles primary-first, so the first entry is it.
 */
export function toFilm(dto: FilmDto): Film {
  return {
    id: dto.id,
    primaryTitle: dto.titles[0].value,
    releaseYear: dto.release_year,
    director: dto.director,
    genres: dto.genre,
    tags: dto.tags,
    posterImage: dto.poster_image,
    averageRating: dto.average_rating,
    isFavorite: dto.is_favorite,
  };
}
