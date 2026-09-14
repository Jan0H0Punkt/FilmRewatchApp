/** `RatingFacade` (DESIGN §6.1): the write DTOs it sends and the local state update it applies on success — no refetch. */
import { HttpClient } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';

import type { RatingEntryDto } from '../film/api';
import { FilmFacade } from '../film/facade';
import { RewatchFacade } from '../rewatch/facade';
import { RatingFacade } from './facade';

/** Stands in for `HttpClient` so the facade is tested without a real backend. */
function stubHttp() {
  return { post: vi.fn().mockReturnValue(of({})), delete: vi.fn().mockReturnValue(of({})) };
}

function stubFilmFacade() {
  return { applyRatingAdded: vi.fn(), applyRatingRemoved: vi.fn() };
}

function stubRewatchFacade() {
  return { removeFilm: vi.fn() };
}

function setUp(
  http: ReturnType<typeof stubHttp>,
  films: ReturnType<typeof stubFilmFacade>,
  rewatch: ReturnType<typeof stubRewatchFacade> = stubRewatchFacade(),
): RatingFacade {
  TestBed.configureTestingModule({
    providers: [
      { provide: HttpClient, useValue: http },
      { provide: FilmFacade, useValue: films },
      { provide: RewatchFacade, useValue: rewatch },
    ],
  });
  return TestBed.inject(RatingFacade);
}

describe('RatingFacade', () => {
  afterEach(() => TestBed.resetTestingModule());

  it('sends an explicit null value for an unrated watch, not an omitted key', async () => {
    const http = stubHttp();
    const facade = setUp(http, stubFilmFacade());

    await new Promise<void>((resolve) => {
      facade.add('f1', { value: null, watchDate: '2024-01-01' }).subscribe(() => resolve());
    });

    expect(http.post).toHaveBeenCalledWith(expect.stringContaining('/films/f1/ratings'), {
      value: null,
      watch_date: '2024-01-01',
    });
  });

  it('sends a rated watch as-is', async () => {
    const http = stubHttp();
    const facade = setUp(http, stubFilmFacade());

    await new Promise<void>((resolve) => {
      facade.add('f1', { value: 4.5, watchDate: '2024-01-01' }).subscribe(() => resolve());
    });

    expect(http.post).toHaveBeenCalledWith(expect.stringContaining('/films/f1/ratings'), {
      value: 4.5,
      watch_date: '2024-01-01',
    });
  });

  it('applies the returned entry to the film locally on success, without reloading anything', async () => {
    const http = stubHttp();
    const entry: RatingEntryDto = {
      id: 'r2',
      value: 4.5,
      watch_date: '2024-01-01',
      created_at: '2024-01-01T00:00:00Z',
    };
    http.post.mockReturnValue(of(entry));
    const films = stubFilmFacade();
    const facade = setUp(http, films);

    await new Promise<void>((resolve) => {
      facade.add('f1', { value: 4.5, watchDate: '2024-01-01' }).subscribe(() => resolve());
    });

    expect(films.applyRatingAdded).toHaveBeenCalledWith('f1', entry);
  });

  it('removes the film from the due-list once its watch is logged', async () => {
    // §6.3: a freshly watched film leaves the rewatch grid at once, from
    // wherever the watch was logged, without waiting for tomorrow's run.
    const http = stubHttp();
    const rewatch = stubRewatchFacade();
    const facade = setUp(http, stubFilmFacade(), rewatch);

    await new Promise<void>((resolve) => {
      facade.add('f1', { value: 4.5, watchDate: '2024-01-01' }).subscribe(() => resolve());
    });

    expect(rewatch.removeFilm).toHaveBeenCalledWith('f1');
  });

  it('does not touch the due-list when the watch fails to save', async () => {
    const http = stubHttp();
    http.post.mockReturnValue(throwError(() => new Error('network error')));
    const rewatch = stubRewatchFacade();
    const facade = setUp(http, stubFilmFacade(), rewatch);

    await new Promise<void>((resolve) => {
      facade.add('f1', { value: 4.5, watchDate: '2024-01-01' }).subscribe({ error: () => resolve() });
    });

    expect(rewatch.removeFilm).not.toHaveBeenCalled();
  });

  it('applies the removal locally when a delete leaves the film in place', async () => {
    const http = stubHttp();
    http.delete.mockReturnValue(of({ rating_id: 'r1', film_id: 'f1', film_deleted: false }));
    const films = stubFilmFacade();
    const facade = setUp(http, films);

    await new Promise<void>((resolve) => {
      facade.remove('r1').subscribe(() => resolve());
    });

    expect(films.applyRatingRemoved).toHaveBeenCalledWith('f1', 'r1', false);
  });

  it('applies the removal locally when a delete removes the film with it', async () => {
    const http = stubHttp();
    http.delete.mockReturnValue(of({ rating_id: 'r1', film_id: 'f1', film_deleted: true }));
    const films = stubFilmFacade();
    const facade = setUp(http, films);

    await new Promise<void>((resolve) => {
      facade.remove('r1').subscribe((result) => {
        expect(result.filmDeleted).toBe(true);
        resolve();
      });
    });

    expect(films.applyRatingRemoved).toHaveBeenCalledWith('f1', 'r1', true);
  });
});
