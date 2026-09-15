/** DTO ↔ domain mapping for films (DESIGN §6.1). Read direction: DTO → domain; write direction: domain → DTO. */
import type { FilmCreateDto, FilmDto, FilmUpdateDto, RatingEntryDto, TitleCreateDto } from './api';
import type { Film, FilmCreateInput, FilmDetail, FilmPatch } from './model';

/**
 * Arithmetic mean of `history`'s *rated* entries (FR-RAT-09/10/11), one
 * decimal, `null` when none are rated. The app's one averaging rule — the
 * backend no longer computes `average_rating` (client-derives-from-history,
 * DESIGN §7.3) — so every caller, including the facade's optimistic rating
 * updates, routes through here rather than re-implementing it.
 */
export function averageRatingOf(history: readonly RatingEntryDto[]): number | null {
  const rated = history.filter((entry): entry is RatingEntryDto & { value: number } => entry.value !== null);
  if (rated.length === 0) return null;
  const mean = rated.reduce((sum, entry) => sum + entry.value, 0) / rated.length;
  return Math.round(mean * 10) / 10;
}

/**
 * Map the §7.3 projection to the domain list model, extracting only the subset
 * the library view renders. The backend guarantees exactly one primary title
 * per film (§5.2 partial unique index), ordered primary-first.
 */
export function toFilm(dto: FilmDto): Film {
  return {
    id: dto.id,
    primaryTitle: dto.titles[0].value,
    releaseYear: dto.release_year,
    director: dto.director,
    runtimeMinutes: dto.runtime_minutes,
    genres: dto.genre,
    tags: dto.tags,
    posterImage: dto.poster_image,
    averageRating: averageRatingOf(dto.rating_history),
    isFavorite: dto.is_favorite,
    titles: dto.titles.map((title) => ({
      value: title.value,
      isPrimary: title.is_primary,
      isOriginal: title.is_original,
    })),
  };
}

/** Map the §7.3 projection to the domain detail model — adds the delay, the history, and the timestamps. */
export function toFilmDetail(dto: FilmDto): FilmDetail {
  return {
    ...toFilm(dto),
    delayDays: dto.delay_days,
    letterboxdUrl: dto.letterboxd_url,
    ratingHistory: dto.rating_history.map((entry) => ({
      id: entry.id,
      value: entry.value,
      watchDate: entry.watch_date,
      createdAt: entry.created_at,
    })),
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  };
}

/**
 * Maps a patch to the wire payload. `JSON.stringify` (what `HttpClient` uses
 * to serialize the body) drops `undefined`-valued keys, so whichever field
 * `patch` left unset never reaches the wire — `FilmUpdate` on the backend
 * treats an absent field as unchanged (FR-LIB-06/07).
 */
export function toFilmUpdateDto(patch: FilmPatch): FilmUpdateDto {
  return {
    is_favorite: patch.isFavorite,
    delay_days: patch.delayDays,
    tags: patch.tags,
    genre: patch.genres,
    letterboxd_url: patch.letterboxdUrl,
  };
}

/**
 * Maps a new-film input to the `POST /films` payload. A flag is sent only
 * when its row set it — an unflagged lone title is what `FilmCreate`'s
 * model validator auto-designates primary (`_titles_with_rules_applied`).
 */
export function toFilmCreateDto(input: FilmCreateInput): FilmCreateDto {
  const titles: TitleCreateDto[] = input.titles.map((title) => ({
    value: title.value,
    ...(title.isPrimary ? { is_primary: true } : {}),
    ...(title.isOriginal ? { is_original: true } : {}),
  }));
  return {
    titles,
    release_year: input.releaseYear,
    director: input.director,
    runtime_minutes: input.runtimeMinutes,
    genre: input.genres,
    tags: input.tags,
    poster_image: input.posterImage,
    letterboxd_url: input.letterboxdUrl,
    first_rating: { value: input.rating, watch_date: input.watchDate },
  };
}
