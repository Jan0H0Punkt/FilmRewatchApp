/** DTO ↔ domain mapping for `letterboxd_url`/`letterboxdUrl` (mirrors `poster_image`, FR-LIB-14/15). */
import type { FilmDto } from './api';
import { toFilmDetail, toFilmUpdateDto } from './mapper';
import type { FilmPatch } from './model';

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
    letterboxd_url: null,
    is_favorite: false,
    delay_days: 0,
    rating_history: [],
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    ...overrides,
  };
}

describe('toFilmDetail', () => {
  it('carries a set letterboxd_url through as letterboxdUrl', () => {
    const detail = toFilmDetail(filmDto({ letterboxd_url: 'https://boxd.it/aaaa' }));
    expect(detail.letterboxdUrl).toBe('https://boxd.it/aaaa');
  });

  it('maps a null letterboxd_url to null', () => {
    const detail = toFilmDetail(filmDto({ letterboxd_url: null }));
    expect(detail.letterboxdUrl).toBeNull();
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
});
