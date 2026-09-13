/** Library view: the ViewModel shaping and the three list states (REQ §7.2). */
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { FilmFacade } from '../../domain/film/facade';
import type { Film } from '../../domain/film/model';
import { Library } from './library';

const HEAT: Film = {
  id: 'f1',
  primaryTitle: 'Heat',
  releaseYear: 1995,
  director: 'Michael Mann',
  runtimeMinutes: 170,
  genres: ['Crime', 'Thriller'],
  tags: ['heist'],
  posterImage: null,
  averageRating: 4,
  isFavorite: true,
};

/** Stands in for the facade so the view is tested without HTTP. */
function stubFacade(films: readonly Film[], isLoading = false, error: unknown = undefined) {
  return {
    films: signal(films),
    isLoading: signal(isLoading),
    error: signal(error),
    reload: vi.fn(),
  };
}

async function render(facade: ReturnType<typeof stubFacade>): Promise<HTMLElement> {
  TestBed.configureTestingModule({
    imports: [Library],
    providers: [provideRouter([]), { provide: FilmFacade, useValue: facade }],
  });
  const fixture = TestBed.createComponent(Library);
  await fixture.whenStable();
  return fixture.nativeElement as HTMLElement;
}

describe('Library', () => {
  afterEach(() => TestBed.resetTestingModule());

  it('renders a film as one row with a joined subtitle and five rating stars', async () => {
    const element = await render(stubFacade([HEAT]));

    expect(element.querySelector('.film__title')?.textContent).toContain('Heat');
    expect(element.querySelector('.film__subtitle')?.textContent).toBe('1995 · Michael Mann · 170 min');
    // The stars are decorative; the one-decimal average is what a screen reader reads.
    const rating = element.querySelector('.film__rating');
    expect(rating?.querySelectorAll('mat-icon')).toHaveLength(5);
    expect(rating?.getAttribute('aria-label')).toBe('Average rating: 4.0 out of 5');
    expect(element.querySelector('.film__favorite')).not.toBeNull();
  });

  it('links each row to its film detail route', async () => {
    const element = await render(stubFacade([HEAT]));

    expect(element.querySelector('.film__link')?.getAttribute('href')).toBe('/film/f1');
  });

  it('shows a dash instead of stars for a film the user chose not to rate', async () => {
    // FR-RAT-13: unrated is not zero stars — it has to read as "no rating given".
    const element = await render(stubFacade([{ ...HEAT, averageRating: null }]));

    const rating = element.querySelector('.film__rating');
    expect(rating?.querySelectorAll('mat-icon')).toHaveLength(0);
    expect(rating?.textContent?.trim()).toBe('—');
    expect(rating?.getAttribute('aria-label')).toBe('Not rated');
  });

  it('renders each genre as its own chip', async () => {
    const element = await render(stubFacade([HEAT]));

    const genres = [...element.querySelectorAll('.film__genre')].map((el) => el.textContent);
    expect(genres).toEqual(['Crime', 'Thriller']);
  });

  it('shows the empty state when the library holds no films', async () => {
    const element = await render(stubFacade([]));

    expect(element.querySelector('.library__list')).toBeNull();
    expect(element.textContent).toContain('No films yet');
  });

  it('shows an error state instead of the list when the request failed', async () => {
    const element = await render(stubFacade([], false, new Error('offline')));

    expect(element.querySelector('.library__list')).toBeNull();
    expect(element.querySelector('[role="alert"]')).not.toBeNull();
  });
});
