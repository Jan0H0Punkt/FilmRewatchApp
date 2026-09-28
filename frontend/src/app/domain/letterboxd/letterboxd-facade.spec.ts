/** Loading and mapping the review list, the three actions, and their failure message. */
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { environment } from '../../../environments/environment';
import { FilmFacade } from '../film/facade';
import type { LetterboxdEntryDto } from './api';
import { LetterboxdFacade } from './facade';

const BASE = `${environment.apiBaseUrl}/letterboxd`;

const DTO: LetterboxdEntryDto = {
  id: 'e1',
  film_title: 'Heat',
  film_year: 1995,
  film_url: 'https://letterboxd.com/film/heat/',
  watched_date: '2026-09-20',
  rating: null,
  rewatch: true,
  suggested_film: { id: 'f1', title: 'Heat' },
};

/** `httpResource`'s loader is async — same settle helper as the settings facade spec. */
async function settle(): Promise<void> {
  await Promise.resolve();
  await Promise.resolve();
  TestBed.tick();
}

describe('LetterboxdFacade', () => {
  let facade: LetterboxdFacade;
  let http: HttpTestingController;
  const films = { reload: vi.fn() };

  beforeEach(() => {
    films.reload.mockReset();
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), { provide: FilmFacade, useValue: films }],
    });
    facade = TestBed.inject(LetterboxdFacade);
    http = TestBed.inject(HttpTestingController);
    TestBed.tick();
  });

  afterEach(() => http.verify());

  it('maps the open entries and counts them', async () => {
    http.expectOne(`${BASE}/entries`).flush([DTO]);
    await settle();

    expect(facade.entries()).toEqual([
      {
        id: 'e1',
        filmTitle: 'Heat',
        filmYear: 1995,
        filmUrl: 'https://letterboxd.com/film/heat/',
        watchedDate: '2026-09-20',
        rating: null,
        rewatch: true,
        suggestedFilm: { id: 'f1', title: 'Heat' },
      },
    ]);
    expect(facade.openCount()).toBe(1);
  });

  it('reads as empty with loadFailed when the list cannot load', async () => {
    http.expectOne(`${BASE}/entries`).flush('down', { status: 500, statusText: 'Server Error' });
    await settle();

    expect(facade.entries()).toEqual([]);
    expect(facade.loadFailed()).toBe(true);
  });

  it('assigns, then reloads the list and the film library', async () => {
    http.expectOne(`${BASE}/entries`).flush([DTO]);
    await settle();

    facade.assign('e1', 'f1');
    const request = http.expectOne({ url: `${BASE}/entries/e1/assign`, method: 'POST' });
    expect(request.request.body).toEqual({ film_id: 'f1' });
    request.flush(null, { status: 204, statusText: 'No Content' });
    await settle();

    expect(films.reload).toHaveBeenCalled();
    http.expectOne(`${BASE}/entries`).flush([]);
    await settle();
    expect(facade.openCount()).toBe(0);
  });

  it('dismisses, then reloads the list', async () => {
    http.expectOne(`${BASE}/entries`).flush([DTO]);
    await settle();

    facade.dismiss('e1');
    http
      .expectOne({ url: `${BASE}/entries/e1/dismiss`, method: 'POST' })
      .flush(null, { status: 204, statusText: 'No Content' });
    await settle();

    http.expectOne(`${BASE}/entries`).flush([]);
  });

  it('syncs, then reloads the list', async () => {
    http.expectOne(`${BASE}/entries`).flush([]);
    await settle();

    facade.sync();
    expect(facade.isBusy()).toBe(true);
    http.expectOne({ url: `${BASE}/sync`, method: 'POST' }).flush({ queued: 1 });
    await settle();

    expect(facade.isBusy()).toBe(false);
    http.expectOne(`${BASE}/entries`).flush([DTO]);
  });

  it('surfaces a failed action and clears it on the next one', async () => {
    http.expectOne(`${BASE}/entries`).flush([DTO]);
    await settle();

    facade.sync();
    http.expectOne({ url: `${BASE}/sync`, method: 'POST' }).flush('down', { status: 502, statusText: 'Bad Gateway' });
    await settle();
    expect(facade.actionError()).toBe('Letterboxd could not be reached.');
    expect(facade.isBusy()).toBe(false);

    facade.dismiss('e1');
    expect(facade.actionError()).toBeNull();
    http
      .expectOne({ url: `${BASE}/entries/e1/dismiss`, method: 'POST' })
      .flush(null, { status: 204, statusText: 'No Content' });
    await settle();
    http.expectOne(`${BASE}/entries`).flush([]);
  });
});
