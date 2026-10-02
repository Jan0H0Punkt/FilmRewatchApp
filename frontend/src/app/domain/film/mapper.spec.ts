/** DTO ↔ domain mapping for `letterboxd_url`/`letterboxdUrl` (mirrors `poster_image`, FR-LIB-14/15) and for film creation. */
import type { FilmDto } from './api';
import { toFilm, toFilmCreateDto, toFilmDetail, toFilmUpdateDto } from './mapper';
import type { FilmCreateInput, FilmPatch } from './model';

function filmDto(overrides: Partial<FilmDto> = {}): FilmDto {
  return {
    id: 'f1',
    titles: [{ value: 'Heat', is_primary: true, is_original: false }],
    release_year: 1995,
    director: 'Michael Mann',
    runtime_minutes: 170,
    genre: ['Crime'],
    tags: [],
    poster_image: null,
    poster_palette: null,
    letterboxd_url: null,
    is_favorite: false,
    owned: false,
    delay_days: 0,
    rating_history: [],
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    ...overrides,
  };
}

describe('toFilm', () => {
  it('takes lastActivityAt from the newest watch when it was logged after the last edit', () => {
    const film = toFilm(
      filmDto({
        rating_history: [
          { id: 'r2', value: 4, watch_date: '2024-03-01', created_at: '2024-03-02T00:00:00Z' },
          { id: 'r1', value: 3, watch_date: '2024-01-01', created_at: '2023-12-01T00:00:00Z' },
        ],
      }),
    );
    expect(film.lastActivityAt).toBe('2024-03-02T00:00:00Z');
  });

  it('keeps updated_at as lastActivityAt when the edit is newer than every watch', () => {
    const film = toFilm(
      filmDto({
        rating_history: [{ id: 'r1', value: 3, watch_date: '2023-12-01', created_at: '2023-12-01T00:00:00Z' }],
      }),
    );
    expect(film.lastActivityAt).toBe('2024-01-01T00:00:00Z');
  });
});

describe('toFilmDetail', () => {
  it('carries a set letterboxd_url through as letterboxdUrl', () => {
    const detail = toFilmDetail(filmDto({ letterboxd_url: 'https://boxd.it/aaaa' }));
    expect(detail.letterboxdUrl).toBe('https://boxd.it/aaaa');
  });

  it('maps a null letterboxd_url to null', () => {
    const detail = toFilmDetail(filmDto({ letterboxd_url: null }));
    expect(detail.letterboxdUrl).toBeNull();
  });

  it('carries a set poster_palette through as posterPalette', () => {
    const detail = toFilmDetail(filmDto({ poster_palette: ['#8a2be2', '#123456'] }));
    expect(detail.posterPalette).toEqual(['#8a2be2', '#123456']);
  });

  it('maps a null poster_palette to null', () => {
    const detail = toFilmDetail(filmDto({ poster_palette: null }));
    expect(detail.posterPalette).toBeNull();
  });
});

describe('toFilmUpdateDto', () => {
  it('sends the link under letterboxd_url when set', () => {
    const patch: FilmPatch = { letterboxdUrl: 'https://boxd.it/aaaa' };
    expect(toFilmUpdateDto(patch).letterboxd_url).toBe('https://boxd.it/aaaa');
  });

  it('sends an explicit null to clear the link', () => {
    const patch: FilmPatch = { letterboxdUrl: null };
    expect(toFilmUpdateDto(patch).letterboxd_url).toBeNull();
  });

  it('drops the key when unset, so JSON.stringify leaves it unchanged on the wire', () => {
    const patch: FilmPatch = {};
    expect(JSON.stringify(toFilmUpdateDto(patch))).not.toContain('letterboxd_url');
  });

  it('maps the record fields the Edit form patches, title flags included', () => {
    const patch: FilmPatch = {
      titles: [
        { value: 'Heat', isPrimary: true, isOriginal: false },
        { value: 'ヒート', isPrimary: false, isOriginal: true },
      ],
      releaseYear: 1995,
      director: 'Michael Mann',
      runtimeMinutes: 170,
      posterImage: null,
    };

    expect(toFilmUpdateDto(patch)).toMatchObject({
      // An unset flag is left out, not sent as `false` — same rule as the create.
      titles: [
        { value: 'Heat', is_primary: true },
        { value: 'ヒート', is_original: true },
      ],
      release_year: 1995,
      director: 'Michael Mann',
      runtime_minutes: 170,
      poster_image: null,
    });
  });
});

function createInput(overrides: Partial<FilmCreateInput> = {}): FilmCreateInput {
  return {
    titles: [{ value: 'Heat', isPrimary: false, isOriginal: false }],
    releaseYear: 1995,
    director: 'Michael Mann',
    runtimeMinutes: 170,
    genres: ['Crime'],
    tags: ['heist'],
    posterImage: null,
    letterboxdUrl: null,
    watchDate: '2024-01-01',
    rating: 4,
    watchedBefore: false,
    owned: false,
    ...overrides,
  };
}

describe('toFilmCreateDto', () => {
  it('sends a single unflagged title as-is (the backend auto-promotes a lone title to primary)', () => {
    const dto = toFilmCreateDto(createInput());
    expect(dto.titles).toEqual([{ value: 'Heat' }]);
  });

  it('sends each flag only when its row set it, in row order', () => {
    const dto = toFilmCreateDto(
      createInput({
        titles: [
          { value: 'Heat', isPrimary: true, isOriginal: false },
          { value: 'Hitze', isPrimary: false, isOriginal: true },
        ],
      }),
    );
    expect(dto.titles).toEqual([
      { value: 'Heat', is_primary: true },
      { value: 'Hitze', is_original: true },
    ]);
  });

  it('maps the scalar fields and the first rating', () => {
    const dto = toFilmCreateDto(createInput());
    expect(dto.release_year).toBe(1995);
    expect(dto.director).toBe('Michael Mann');
    expect(dto.runtime_minutes).toBe(170);
    expect(dto.genre).toEqual(['Crime']);
    expect(dto.tags).toEqual(['heist']);
    expect(dto.poster_image).toBeNull();
    expect(dto.first_rating).toEqual({ value: 4, watch_date: '2024-01-01' });
  });

  it('sends a set letterboxd_url', () => {
    const dto = toFilmCreateDto(createInput({ letterboxdUrl: 'https://boxd.it/aaaa' }));
    expect(dto.letterboxd_url).toBe('https://boxd.it/aaaa');
  });

  it('sends an explicit null rating for "do not rate this"', () => {
    const dto = toFilmCreateDto(createInput({ rating: null }));
    expect(dto.first_rating).toEqual({ value: null, watch_date: '2024-01-01' });
  });
});
