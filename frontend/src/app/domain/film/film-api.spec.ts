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
    letterboxd_url: null,
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

/**
 * Opening the detail view directly (a reload on `/films/{id}`) starts both
 * requests at once, with no list to look the id up in yet. The library must
 * still end up whole — writing a resolved fallback into `list` while its own
 * request is in flight would abort that request and strand the library at
 * the single folded-in film.
 */
describe('FilmApi with the detail view opened before the library lands', () => {
  let api: FilmApi;
  let httpTesting: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    api = TestBed.inject(FilmApi);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    TestBed.resetTestingModule();
  });

  it('still ends up with the whole library', async () => {
    TestBed.tick();
    const listRequest = httpTesting.expectOne(`${environment.apiBaseUrl}/films`);

    // The detail route's id, selected while `GET /films` is still in flight.
    api.selectedId.set('f2');
    TestBed.tick();

    // No fallback yet: it would race the library load and cancel it.
    httpTesting.expectNone(`${environment.apiBaseUrl}/films/f2`);

    listRequest.flush([filmDto({ id: 'f1' }), filmDto({ id: 'f2' }), filmDto({ id: 'f3' })]);
    await Promise.resolve();
    await Promise.resolve();
    TestBed.tick();

    expect(api.list.value().map((film) => film.id)).toEqual(['f1', 'f2', 'f3']);
    // The library carried the selected film all along, so it never fires.
    httpTesting.expectNone(`${environment.apiBaseUrl}/films/f2`);
  });

  it('falls back once the library has landed without the selected film', async () => {
    TestBed.tick();
    const listRequest = httpTesting.expectOne(`${environment.apiBaseUrl}/films`);

    api.selectedId.set('f9');
    TestBed.tick();
    listRequest.flush([filmDto({ id: 'f1' })]);
    await Promise.resolve();
    await Promise.resolve();
    TestBed.tick();

    httpTesting.expectOne(`${environment.apiBaseUrl}/films/f9`).flush(filmDto({ id: 'f9' }));
    await Promise.resolve();
    await Promise.resolve();
    TestBed.tick();

    expect(api.list.value().map((film) => film.id)).toEqual(['f1', 'f9']);
  });
});

/**
 * The decisive unguarded reader (residual-fix review): `detail`'s request
 * factory reads `this.list.value()` and runs inside `list`'s own effect, so
 * it re-evaluates on every tick regardless of whether anything ever reads
 * `detail` itself. A failed `/films` reload while a film stays selected
 * therefore crashes purely from ticking change detection — no template, no
 * `FilmFacade` read, required.
 */
describe('FilmApi.detail when list has errored', () => {
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

  it('does not crash the effect flush, and makes no fallback request, once list has errored', async () => {
    // Selects a film already in `list` — no fallback fetch, exactly like
    // opening the detail view for a film the library already has.
    api.selectedId.set('f1');
    TestBed.tick();

    // A later reload (re-opening a view that refetches) fails. `selectedId`
    // was never cleared, so `detail`'s factory re-evaluates on the next tick
    // even though nothing here ever reads `api.detail` itself.
    api.list.reload();
    TestBed.tick();
    httpTesting.expectOne(`${environment.apiBaseUrl}/films`).flush('boom', { status: 500, statusText: 'Server Error' });
    // `httpResource` settles an errored response through a microtask (its
    // loader is async) — see the fold-in test above for the same pattern.
    await Promise.resolve();
    await Promise.resolve();

    expect(() => TestBed.tick()).not.toThrow();
    httpTesting.expectNone(`${environment.apiBaseUrl}/films/f1`);
  });
});
