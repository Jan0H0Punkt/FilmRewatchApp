/** The join, the order guarantee, and the §6.3 optimistic removal. */
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { environment } from '../../../environments/environment';
import { Rewatch } from '../../views/rewatch/rewatch';
import { FilmFacade } from '../film/facade';
import type { Film } from '../film/model';
import type { RewatchSuggestionDto } from './api';
import { RewatchApi } from './api';
import { RewatchFacade } from './facade';

function film(id: string, title: string, rating: number | null = 4): Film {
  return {
    id,
    primaryTitle: title,
    releaseYear: 1995,
    director: 'Michael Mann',
    runtimeMinutes: 170,
    genres: [],
    tags: [],
    posterImage: null,
    averageRating: rating,
    isFavorite: false,
    titles: [{ value: title, isPrimary: true, isOriginal: true }],
  };
}

function configure(films: readonly Film[], suggestions: readonly RewatchSuggestionDto[]) {
  const value = signal<readonly RewatchSuggestionDto[]>(suggestions);
  const apiStub = {
    list: {
      value,
      status: signal('resolved' as const),
      isLoading: signal(false),
      error: signal(undefined),
      reload: (): void => undefined,
    },
    removeFilm: (filmId: string): void =>
      value.update((suggestions) => suggestions.filter((s) => s.film_id !== filmId)),
  };
  TestBed.configureTestingModule({
    providers: [
      { provide: RewatchApi, useValue: apiStub },
      {
        provide: FilmFacade,
        useValue: { films: signal(films), isLoading: signal(false), error: signal(undefined) },
      },
    ],
  });
  return { facade: TestBed.inject(RewatchFacade), value };
}

describe('RewatchFacade', () => {
  it('joins each suggestion to its film', () => {
    const { facade } = configure([film('f1', 'Heat')], [{ film_id: 'f1', days_until_next_rewatch: -2 }]);

    expect(facade.cards().map((card) => [card.title, card.dueLabel])).toEqual([['Heat', 'Overdue by 2 days']]);
  });

  it('keeps the suggestion order even when the library is ordered differently', () => {
    // FR-RW-04: the client never re-sorts the algorithm's output.
    const { facade } = configure(
      [film('f1', 'Heat'), film('f2', 'Se7en')],
      [
        { film_id: 'f2', days_until_next_rewatch: -40 },
        { film_id: 'f1', days_until_next_rewatch: 0 },
      ],
    );

    expect(facade.cards().map((card) => card.title)).toEqual(['Se7en', 'Heat']);
  });

  it('skips a suggestion whose film the library does not hold', () => {
    const { facade } = configure(
      [film('f1', 'Heat')],
      [
        { film_id: 'ghost', days_until_next_rewatch: -9 },
        { film_id: 'f1', days_until_next_rewatch: 0 },
      ],
    );

    expect(facade.cards().map((card) => card.title)).toEqual(['Heat']);
  });

  it('removes exactly one film from the due-list on request', () => {
    const { facade } = configure(
      [film('f1', 'Heat'), film('f2', 'Se7en')],
      [
        { film_id: 'f1', days_until_next_rewatch: -1 },
        { film_id: 'f2', days_until_next_rewatch: -2 },
      ],
    );

    facade.removeFilm('f1');

    expect(facade.cards().map((card) => card.title)).toEqual(['Se7en']);
  });

  it('ignores a removal for a film that is not due', () => {
    const { facade } = configure([film('f1', 'Heat')], [{ film_id: 'f1', days_until_next_rewatch: 0 }]);

    facade.removeFilm('f2');

    expect(facade.cards()).toHaveLength(1);
  });

  it('has no cards for an empty due-list', () => {
    const { facade } = configure([film('f1', 'Heat')], []);

    expect(facade.cards()).toEqual([]);
  });
});

/** A `FilmFacade` stub for the tests below — they drive `/rewatch-suggestions` through a real `RewatchApi`; the library side is not under test here. */
function filmFacadeStub(films: readonly Film[] = [film('f1', 'Heat')]) {
  return { films: signal(films), isLoading: signal(false), error: signal(undefined), reload: (): void => undefined };
}

/**
 * CRITICAL 1/2 (final whole-branch review): the tests above replace `RewatchApi`
 * with a plain-signal stub, which cannot reproduce the actual bug — Angular 22's
 * `httpResource.value()` throws `ResourceValueError` once the resource is in the
 * error state, rather than falling back to `defaultValue`. These tests instead
 * run the REAL `RewatchApi` against `HttpTestingController`, so a regression of
 * the `linkedSignal` guard in `RewatchFacade`/`FilmFacade` fails here for real.
 *
 * Confirmed failing pre-fix: with `RewatchFacade.cards` and `FilmFacade.films`
 * reading `api.list.value()` directly (no guard), the "keeps the last
 * successful cards" test below failed with the exact throw this fix
 * prevents — `cards()` threw "Error: Resource is currently in an error
 * state (see Error.cause for details): Http failure response for
 * .../rewatch-suggestions: 500 Internal Server Error" instead of returning
 * the prior due-list — exactly FR-RW-07's landing-route freeze.
 */
describe('RewatchFacade against a real RewatchApi', () => {
  let httpTesting: HttpTestingController;
  let facade: RewatchFacade;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), { provide: FilmFacade, useValue: filmFacadeStub() }],
    });
    httpTesting = TestBed.inject(HttpTestingController);
    facade = TestBed.inject(RewatchFacade);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  it('keeps the last successful cards on screen, without throwing, after a later fetch fails', async () => {
    TestBed.tick();
    httpTesting
      .expectOne(`${environment.apiBaseUrl}/rewatch-suggestions`)
      .flush([{ film_id: 'f1', days_until_next_rewatch: -1 }]);
    await Promise.resolve();
    await Promise.resolve();
    TestBed.tick();

    expect(facade.cards().map((card) => card.title)).toEqual(['Heat']);
    expect(facade.error()).toBeUndefined();

    facade.reload();
    TestBed.tick();
    httpTesting
      .expectOne(`${environment.apiBaseUrl}/rewatch-suggestions`)
      .flush('boom', { status: 500, statusText: 'Internal Server Error' });
    await Promise.resolve();
    await Promise.resolve();
    TestBed.tick();

    // 1. Reading `cards()` after the error must not throw.
    expect(() => facade.cards()).not.toThrow();
    // 2. The prior successful fetch's cards survive the failure.
    expect(facade.cards().map((card) => card.title)).toEqual(['Heat']);
    // 3. The error is surfaced for the banner.
    expect(facade.error()).toBeDefined();
  });
});

/** IMPORTANT 5: exercises the real `removeFilm`, not a hand-duplicated filter — breaking `api.ts` should fail here, unlike the stub-based tests above. */
describe('RewatchApi', () => {
  let api: RewatchApi;
  let httpTesting: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    api = TestBed.inject(RewatchApi);
    httpTesting = TestBed.inject(HttpTestingController);

    TestBed.tick();
    httpTesting.expectOne(`${environment.apiBaseUrl}/rewatch-suggestions`).flush([
      { film_id: 'f1', days_until_next_rewatch: -1 },
      { film_id: 'f2', days_until_next_rewatch: -2 },
    ]);
    TestBed.tick();
  });

  afterEach(() => {
    httpTesting.verify();
  });

  it('removes exactly the requested film from the cached list, locally, with no request', () => {
    api.removeFilm('f1');

    expect(api.list.value().map((suggestion) => suggestion.film_id)).toEqual(['f2']);
    httpTesting.expectNone(`${environment.apiBaseUrl}/rewatch-suggestions`);
  });
});

/** IMPORTANT 6: the view re-reads on open (design §4.3) — opening it a second time must re-issue the fetch, not just replay the first one. */
describe('opening the Rewatch view', () => {
  let httpTesting: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [Rewatch],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: FilmFacade, useValue: filmFacadeStub([]) },
      ],
    });
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  it('fetches once on the first open and again on a later re-open, not twice on the first', async () => {
    const first = TestBed.createComponent(Rewatch);
    TestBed.tick();
    httpTesting.expectOne(`${environment.apiBaseUrl}/rewatch-suggestions`).flush([]);
    await Promise.resolve();
    await Promise.resolve();
    TestBed.tick();
    first.destroy();

    const second = TestBed.createComponent(Rewatch);
    TestBed.tick();
    await Promise.resolve();
    await Promise.resolve();
    TestBed.tick();
    httpTesting.expectOne(`${environment.apiBaseUrl}/rewatch-suggestions`).flush([]);
    second.destroy();
  });
});
