/**
 * `FilmFacade` (DESIGN §6.1): writes update `list` locally instead of
 * refetching — a PATCH applies immediately and rolls back on error, and a
 * successful write never issues a GET. `detail` is a plain lookup into
 * `list`, so every assertion below reaches it through `facade.detail()`
 * without a second resource to keep in sync.
 */
import { HttpErrorResponse, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';

import { environment } from '../../../environments/environment';
import type { FilmDto } from './api';
import { FilmApi } from './api';
import { FilmFacade } from './facade';

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
    rating_history: [{ id: 'r1', value: 4, watch_date: '2024-01-01', created_at: '2024-01-01T00:00:00Z' }],
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    ...overrides,
  };
}

/**
 * A writable-signal stand-in for `httpResource.value`/`selectedId`, matching
 * the shape the facade relies on. Backed by a real `signal()` — not a plain
 * closure — so it stays reactive: `FilmFacade.listSafe` (a `linkedSignal`
 * layered over `list.value`) only re-derives when a real signal write
 * invalidates it, same as production's `httpResource.value`. `.set`/`.update`
 * stay spies (`toHaveBeenCalledWith` assertions below) wrapping the real ones.
 */
function valueSignal<T>(initial: T) {
  const sig = signal(initial) as unknown as { (): T; set: (v: T) => void; update: (fn: (v: T) => T) => void };
  const realSet = sig.set.bind(sig);
  const realUpdate = sig.update.bind(sig);
  sig.set = vi.fn(realSet);
  sig.update = vi.fn(realUpdate);
  return sig;
}

/** Stands in for `FilmApi` so the facade is tested without a real backend. `detailError` stubs the fallback `GET /films/{id}`'s outcome. */
function stubApi(list: readonly FilmDto[] = [], selectedId: string | null = null, detailError: unknown = undefined) {
  return {
    list: {
      value: valueSignal(list),
      status: () => 'resolved' as const,
      isLoading: () => false,
      error: () => undefined,
      reload: vi.fn(),
    },
    detail: { isLoading: () => false, error: () => detailError, reload: vi.fn() },
    selectedId: valueSignal(selectedId),
    update: vi.fn(),
    remove: vi.fn().mockReturnValue(of(undefined)),
  };
}

function setUp(api: ReturnType<typeof stubApi>): FilmFacade {
  TestBed.configureTestingModule({ providers: [{ provide: FilmApi, useValue: api }] });
  return TestBed.inject(FilmFacade);
}

describe('FilmFacade', () => {
  afterEach(() => TestBed.resetTestingModule());

  describe('detail', () => {
    it('finds the selected film in the list', () => {
      const facade = setUp(stubApi([filmDto()], 'f1'));

      expect(facade.detail()?.id).toBe('f1');
    });

    it('is null when nothing is selected', () => {
      const facade = setUp(stubApi([filmDto()], null));

      expect(facade.detail()).toBeNull();
    });

    it('is null when the selected id is not in the list', () => {
      const facade = setUp(stubApi([filmDto()], 'missing'));

      expect(facade.detail()).toBeNull();
    });
  });

  describe('detailNotFound', () => {
    it('is true once the fallback fetch settles with a 404', () => {
      const facade = setUp(stubApi([], 'missing', new HttpErrorResponse({ status: 404 })));

      expect(facade.detailNotFound()).toBe(true);
      expect(facade.detailError()).toBeUndefined();
    });

    it('is false for any other failure, which surfaces as detailError instead', () => {
      const facade = setUp(stubApi([], 'missing', new HttpErrorResponse({ status: 500 })));

      expect(facade.detailNotFound()).toBe(false);
      expect(facade.detailError()).toBeTruthy();
    });
  });

  describe('update()', () => {
    it('applies the patch to the list immediately, before the request resolves', () => {
      const heat = filmDto();
      const api = stubApi([heat], 'f1');
      // Never resolves — proves the local update happens synchronously, not in a `tap`.
      api.update.mockReturnValue({ pipe: () => ({ subscribe: () => undefined }) });
      const facade = setUp(api);

      facade.update('f1', { isFavorite: true });

      expect(facade.detail()?.isFavorite).toBe(true);
      expect(facade.films()[0]?.isFavorite).toBe(true);
    });

    it('merges the response body in on success, without issuing a GET', async () => {
      const heat = filmDto();
      const api = stubApi([heat], 'f1');
      const updated = filmDto({ is_favorite: true, updated_at: '2024-02-01T00:00:00Z' });
      api.update.mockReturnValue(of(updated));
      const facade = setUp(api);

      await new Promise<void>((resolve) => {
        facade.update('f1', { isFavorite: true }).subscribe(() => resolve());
      });

      expect(facade.detail()?.updatedAt).toBe('2024-02-01T00:00:00Z');
      expect(api.list.reload).not.toHaveBeenCalled();
      expect(api.detail.reload).not.toHaveBeenCalled();
    });

    it('rolls the value back when the request fails', async () => {
      const heat = filmDto({ is_favorite: false });
      const api = stubApi([heat], 'f1');
      api.update.mockReturnValue(throwError(() => new Error('network error')));
      const facade = setUp(api);

      await new Promise<void>((resolve) => {
        facade.update('f1', { isFavorite: true }).subscribe({ error: () => resolve() });
      });

      expect(facade.detail()?.isFavorite).toBe(false);
      expect(facade.films()[0]?.isFavorite).toBe(false);
    });

    it('still surfaces the error to the caller after rolling back', async () => {
      const heat = filmDto();
      const api = stubApi([heat], 'f1');
      const failure = new Error('network error');
      api.update.mockReturnValue(throwError(() => failure));
      const facade = setUp(api);

      const error = await new Promise<unknown>((resolve) => {
        facade.update('f1', { isFavorite: true }).subscribe({ error: resolve });
      });

      expect(error).toBe(failure);
    });

    it('leaves the untouched field alone when rolling back a different field', async () => {
      const heat = filmDto({ is_favorite: true, delay_days: 3 });
      const api = stubApi([heat], 'f1');
      api.update.mockReturnValue(throwError(() => new Error('fail')));
      const facade = setUp(api);

      await new Promise<void>((resolve) => {
        facade.update('f1', { delayDays: 7 }).subscribe({ error: () => resolve() });
      });

      expect(facade.detail()?.delayDays).toBe(3);
      expect(facade.detail()?.isFavorite).toBe(true);
    });
  });

  describe('applyRatingAdded()', () => {
    it('prepends the entry and recomputes the average', () => {
      const heat = filmDto({
        rating_history: [{ id: 'r1', value: 3, watch_date: '2024-01-01', created_at: '2024-01-01T00:00:00Z' }],
      });
      const api = stubApi([heat], 'f1');
      const facade = setUp(api);

      facade.applyRatingAdded('f1', {
        id: 'r2',
        value: 5,
        watch_date: '2024-02-01',
        created_at: '2024-02-01T00:00:00Z',
      });

      expect(facade.detail()?.ratingHistory.map((entry) => entry.id)).toEqual(['r2', 'r1']);
      expect(facade.detail()?.averageRating).toBe(4);
      expect(facade.films()[0]?.averageRating).toBe(4);
    });

    it('ignores unrated entries when recomputing the average', () => {
      const heat = filmDto({
        rating_history: [{ id: 'r1', value: 3, watch_date: '2024-01-01', created_at: '2024-01-01T00:00:00Z' }],
      });
      const api = stubApi([heat], 'f1');
      const facade = setUp(api);

      facade.applyRatingAdded('f1', {
        id: 'r2',
        value: null,
        watch_date: '2024-02-01',
        created_at: '2024-02-01T00:00:00Z',
      });

      expect(facade.detail()?.averageRating).toBe(3);
    });
  });

  describe('applyRatingRemoved()', () => {
    it('removes the entry and recomputes the average when the film survives', () => {
      const heat = filmDto({
        rating_history: [
          { id: 'r1', value: 3, watch_date: '2024-01-01', created_at: '2024-01-01T00:00:00Z' },
          { id: 'r2', value: 5, watch_date: '2024-02-01', created_at: '2024-02-01T00:00:00Z' },
        ],
      });
      const api = stubApi([heat], 'f1');
      const facade = setUp(api);

      facade.applyRatingRemoved('f1', 'r2', false);

      expect(facade.detail()?.ratingHistory.map((entry) => entry.id)).toEqual(['r1']);
      expect(facade.detail()?.averageRating).toBe(3);
    });

    it('drops the film from the list and clears selection when it was the last rating', () => {
      const heat = filmDto();
      const api = stubApi([heat], 'f1');
      const facade = setUp(api);

      facade.applyRatingRemoved('f1', 'r1', true);

      expect(facade.films()).toEqual([]);
      expect(api.selectedId.set).toHaveBeenCalledWith(null);
    });
  });

  describe('remove()', () => {
    it('removes the film from the list and clears the selection on success', async () => {
      const heat = filmDto();
      const api = stubApi([heat], 'f1');
      const facade = setUp(api);

      await new Promise<void>((resolve) => {
        facade.remove('f1').subscribe(() => resolve());
      });

      expect(facade.films()).toEqual([]);
      expect(api.selectedId.set).toHaveBeenCalledWith(null);
      expect(api.list.reload).not.toHaveBeenCalled();
    });
  });
});

/**
 * The residual-fix review's repro, against the real `FilmApi` (the stub in
 * `stubApi` above has a constant `status` and a plain-function `value`, so it
 * cannot exercise the error-state throw `httpResource.value()` performs in
 * Angular 22). Sequence: open Rewatch (`/films` loads), click a film card
 * (`select`), navigate back (`selectedId` is never cleared — see `FilmApi`),
 * then a later `/films` reload fails. This is the facade-level equivalent of
 * the reviewer's rendered-component repro (Rewatch → film card → back →
 * `/films` fails); a true component-level version would additionally have to
 * mount `FilmDetail`, which pulls in `GenreFacade`/`TagFacade`/`RatingFacade`
 * and `MatDialog` — machinery unrelated to this resource-throw bug — so this
 * drives the same code path through the facade instead.
 *
 * Per the reviewer's note: `listSafe` is a `linkedSignal`, so it only
 * preserves a value that was actually READ before the error. The reads below
 * (`facade.films()`/`facade.detail()`) before the failing reload stand in for
 * the template re-rendering every frame in the running app.
 */
describe('FilmFacade against a real FilmApi, once list has errored', () => {
  let httpTesting: HttpTestingController;

  async function loadTwoFilms(): Promise<FilmFacade> {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    const facade = TestBed.inject(FilmFacade);
    httpTesting = TestBed.inject(HttpTestingController);

    TestBed.tick();
    httpTesting
      .expectOne(`${environment.apiBaseUrl}/films`)
      .flush([
        filmDto({ id: 'f1' }),
        filmDto({ id: 'f2', titles: [{ value: 'Mulholland Drive', is_primary: true, is_original: false }] }),
      ]);
    // `httpResource`'s loader is async even for a same-tick `flush` — see the
    // fold-in test in `film-api.spec.ts` for the same pattern.
    await Promise.resolve();
    await Promise.resolve();
    TestBed.tick();
    return facade;
  }

  afterEach(() => {
    httpTesting.verify();
    TestBed.resetTestingModule();
  });

  it('keeps the last good library and selected film readable after select, then a failing reload', async () => {
    const facade = await loadTwoFilms();

    // Click a film card: `FilmDetail`'s constructor effect calls `select`.
    facade.select('f1');
    TestBed.tick();
    httpTesting.expectNone(`${environment.apiBaseUrl}/films/f1`); // already in the list, no fallback fetch

    // The template reads these every render — priming `listSafe` the same way.
    expect(facade.films().map((film) => film.id)).toEqual(['f1', 'f2']);
    expect(facade.detail()?.id).toBe('f1');

    // Navigate back: nothing clears `selectedId` (see `FilmApi.selectedId`'s
    // docstring) — it stays 'f1'. A later reload (Rewatch reopening, say)
    // then fails.
    facade.reload();
    TestBed.tick();
    httpTesting.expectOne(`${environment.apiBaseUrl}/films`).flush('boom', { status: 500, statusText: 'Server Error' });
    // `httpResource` settles an errored response through a microtask (its
    // loader is async), so the effect that recomputes `api.detail`'s request
    // (the decisive unguarded read, api.ts's `detail`) needs an actual tick
    // of the microtask queue before a further `TestBed.tick()` reaches it.
    await Promise.resolve();
    await Promise.resolve();

    expect(() => TestBed.tick()).not.toThrow();

    // Reading state afterwards must not throw either, and must surface the
    // failure as an error — not silently empty the library.
    expect(() => facade.films()).not.toThrow();
    expect(facade.error()).toBeTruthy();
    expect(facade.films().map((film) => film.id)).toEqual(['f1', 'f2']);
    expect(facade.detail()?.id).toBe('f1');
  });
});
