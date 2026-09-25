/** DTO → domain mapping, month labels, error state, and refetch on reopen. */
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { environment } from '../../../environments/environment';
import type { StatsBlockDto, StatsDto } from './api';
import { StatsFacade } from './facade';

const URL = `${environment.apiBaseUrl}/stats`;

function block(overrides: Partial<StatsBlockDto> = {}): StatsBlockDto {
  return {
    watches: 3,
    first_watches: 1,
    rewatches: 2,
    films_released_that_year: null,
    distinct_films: 1,
    minutes_watched: 510,
    average_rating: 4.5,
    rating_distribution: [{ value: 4.5, count: 3 }],
    top_genres: [{ name: 'Crime', count: 3 }],
    top_directors: [{ name: 'Michael Mann', count: 3 }],
    top_films: [{ film_id: 'f1', title: 'Heat', watches: 3, average_rating: 4.5, score: 13.5 }],
    buckets: [{ label: '2026', count: 3 }],
    ...overrides,
  };
}

const PAYLOAD: StatsDto = {
  total: block(),
  years: [
    {
      year: 2026,
      ...block({
        films_released_that_year: 0,
        buckets: [
          { label: '1', count: 0 },
          { label: '3', count: 3 },
        ],
      }),
    },
  ],
};

/**
 * `httpResource` resolves a flushed response through a microtask (its loader
 * is async, same as `FilmApi`'s spec) — a plain `TestBed.tick()` right after
 * `flush()` is not enough, so every assertion below waits a tick of the
 * microtask queue first.
 */
async function settle(): Promise<void> {
  await Promise.resolve();
  await Promise.resolve();
  TestBed.tick();
}

describe('StatsFacade', () => {
  let facade: StatsFacade;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    facade = TestBed.inject(StatsFacade);
    http = TestBed.inject(HttpTestingController);
    TestBed.tick();
  });

  afterEach(() => http.verify());

  it('maps the payload to camelCase domain models', async () => {
    http.expectOne(URL).flush(PAYLOAD);
    await settle();

    const stats = facade.stats();
    expect(stats?.total.firstWatches).toBe(1);
    expect(stats?.total.filmsReleasedThatYear).toBeNull();
    expect(stats?.total.topFilms).toEqual([
      { filmId: 'f1', title: 'Heat', watches: 3, averageRating: 4.5, score: 13.5 },
    ]);
    expect(stats?.years[0].year).toBe(2026);
    expect(stats?.years[0].filmsReleasedThatYear).toBe(0);
  });

  it('labels year buckets with month names and leaves all-time buckets as years', async () => {
    http.expectOne(URL).flush(PAYLOAD);
    await settle();

    expect(facade.stats()?.years[0].buckets.map((b) => b.label)).toEqual(['Jan', 'Mar']);
    expect(facade.stats()?.total.buckets.map((b) => b.label)).toEqual(['2026']);
  });

  it('exposes an error and no stats when the request fails', async () => {
    http.expectOne(URL).flush('down', { status: 500, statusText: 'Server Error' });
    await settle();

    expect(facade.stats()).toBeNull();
    expect(facade.error()).toBeTruthy();
  });

  it('refetches when the view is opened again', async () => {
    facade.onViewOpened();
    http.expectOne(URL).flush(PAYLOAD);
    await settle();

    facade.onViewOpened();
    await settle();
    http.expectOne(URL).flush(PAYLOAD);
  });
});
