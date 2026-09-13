/**
 * `FilmApi` (DESIGN §6.1): `detail`'s `GET /films/{id}` is a fallback for a
 * `selectedId` that `list` doesn't hold — the common case (already in
 * `list`) must make no second request, and a resolved fallback must fold
 * back into `list` so it stays the single source of truth.
 */
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { environment } from '../../../environments/environment';
import type { FilmDto } from './api';
import { FilmApi } from './api';

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
    is_favorite: false,
    delay_days: 0,
    rating_history: [],
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    ...overrides,
  };
}

describe('FilmApi', () => {
  let api: FilmApi;
  let httpTesting: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    api = TestBed.inject(FilmApi);
    httpTesting = TestBed.inject(HttpTestingController);

    TestBed.tick();
    httpTesting.expectOne(`${environment.apiBaseUrl}/films`).flush([filmDto({ id: 'f1' })]);
    TestBed.tick();
  });

  afterEach(() => {
    httpTesting.verify();
    TestBed.resetTestingModule();
  });

  it('makes no request for a film already in the list', () => {
    api.selectedId.set('f1');
    TestBed.tick();

    httpTesting.expectNone(`${environment.apiBaseUrl}/films/f1`);
  });

  it('fetches the film as a fallback when it is missing from the list, then folds it in', async () => {
    api.selectedId.set('f2');
    TestBed.tick();

    const req = httpTesting.expectOne(`${environment.apiBaseUrl}/films/f2`);
    req.flush(filmDto({ id: 'f2' }));
    // `httpResource` resolves the response through a microtask (its loader
    // is async), so the fold-in effect needs an actual tick of the
    // microtask queue before `TestBed.tick()` can flush it.
    await Promise.resolve();
    await Promise.resolve();
    TestBed.tick();

    expect(api.list.value().map((film) => film.id)).toEqual(['f1', 'f2']);
  });
});
