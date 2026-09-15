/** Library view: the ViewModel shaping, the search filter (FR-SF-01..05), and the list states (REQ §7.2). */
import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
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
  titles: [{ value: 'Heat', isPrimary: true, isOriginal: true }],
};

/** Carries an alternative (non-primary) title, distinct from its primary one — proves FR-SF-01 matches beyond `primaryTitle`. */
const SEVEN: Film = {
  id: 'f2',
  primaryTitle: 'Se7en',
  releaseYear: 1995,
  director: 'David Fincher',
  runtimeMinutes: 127,
  genres: ['Crime', 'Drama'],
  tags: [],
  posterImage: null,
  averageRating: null,
  isFavorite: false,
  titles: [
    { value: 'Se7en', isPrimary: true, isOriginal: true },
    { value: 'Seven', isPrimary: false, isOriginal: false },
  ],
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

/** The most recently created fixture — lets a test drive the search input and await the change it causes. */
let currentFixture: ComponentFixture<Library>;

async function render(facade: ReturnType<typeof stubFacade>): Promise<HTMLElement> {
  TestBed.configureTestingModule({
    imports: [Library],
    providers: [provideRouter([]), { provide: FilmFacade, useValue: facade }],
  });
  currentFixture = TestBed.createComponent(Library);
  await currentFixture.whenStable();
  return currentFixture.nativeElement as HTMLElement;
}

/** Types into the search field the way a real keystroke would — sets `.value`, then fires the native `input` event. */
async function search(element: HTMLElement, query: string): Promise<void> {
  const input = element.querySelector<HTMLInputElement>('.library__search input')!;
  input.value = query;
  input.dispatchEvent(new Event('input'));
  await currentFixture.whenStable();
}

describe('Library', () => {
  afterEach(() => TestBed.resetTestingModule());

  it('renders a film as one row with a joined subtitle and five rating stars', async () => {
    const element = await render(stubFacade([HEAT]));

    expect(element.querySelector('.film__title')?.textContent).toContain('Heat');
    expect(element.querySelector('.film__subtitle')?.textContent).toBe('1995 • Michael Mann • 170 min');
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

  it('shows the empty state when the library holds no films, with a way to add the first one', async () => {
    const element = await render(stubFacade([]));

    expect(element.querySelector('.library__list')).toBeNull();
    expect(element.textContent).toContain('No films yet');
    // Searching an empty library is pointless — the field shouldn't even appear.
    expect(element.querySelector('.library__search')).toBeNull();
    expect(element.querySelector<HTMLAnchorElement>('a.library__add')?.getAttribute('href')).toBe('/films/new');
  });

  it('shows an error state instead of the list when the request failed', async () => {
    const element = await render(stubFacade([], false, new Error('offline')));

    expect(element.querySelector('.library__list')).toBeNull();
    expect(element.querySelector('[role="alert"]')).not.toBeNull();
  });

  it('focuses the search field on arrival, so the view is type-ready', async () => {
    const element = await render(stubFacade([HEAT]));

    expect(document.activeElement).toBe(element.querySelector('.library__search input'));
  });

  it('has an Add Film button that focuses the search field — the one path into the create flow', async () => {
    const element = await render(stubFacade([HEAT]));
    const input = element.querySelector<HTMLInputElement>('.library__search input')!;
    input.blur();

    element.querySelector<HTMLButtonElement>('.library__add-button')!.click();
    await currentFixture.whenStable();

    expect(document.activeElement).toBe(input);
  });

  describe('title search (FR-SF-01..05)', () => {
    it('shows the unfiltered count when nothing is searched', async () => {
      const element = await render(stubFacade([HEAT, SEVEN]));

      expect(element.querySelector('.library__count')?.textContent).toBe('2 films');
    });

    it('narrows the list to films whose title matches the query', async () => {
      const element = await render(stubFacade([HEAT, SEVEN]));

      await search(element, 'heat');

      const titles = element.querySelectorAll('.film__title');
      expect(titles).toHaveLength(1);
      expect(titles[0]?.textContent).toContain('Heat');
    });

    it('matches an alternative (non-primary) title, not just the primary one', async () => {
      const element = await render(stubFacade([HEAT, SEVEN]));

      await search(element, 'seven');

      const titles = element.querySelectorAll('.film__title');
      expect(titles).toHaveLength(1);
      expect(titles[0]?.textContent).toContain('Se7en');
    });

    it('reads "X of Y films" once filtered', async () => {
      const element = await render(stubFacade([HEAT, SEVEN]));

      await search(element, 'heat');

      expect(element.querySelector('.library__count')?.textContent).toBe('1 of 2 films');
    });

    it('shows only the "+ Add new film" link, not the "No films yet" empty state, for a query with no hits', async () => {
      const element = await render(stubFacade([HEAT, SEVEN]));

      await search(element, 'nonexistent');

      expect(element.querySelector('.library__list')).toBeNull();
      expect(element.textContent).not.toContain('No films yet');
      const addLink = element.querySelector<HTMLAnchorElement>('a.library__add');
      expect(addLink?.textContent).toContain('Add new film');
      expect(addLink?.getAttribute('href')).toBe('/films/new?title=nonexistent');
    });

    it('adds a "+ Add new film" entry at the end of the matches once a title is typed', async () => {
      const element = await render(stubFacade([HEAT, SEVEN]));

      await search(element, 'heat');

      const list = element.querySelector('.library__list')!;
      const addLink = list.querySelector<HTMLAnchorElement>('a.library__add');
      expect(addLink).not.toBeNull();
      expect(addLink?.getAttribute('href')).toBe('/films/new?title=heat');
    });

    it('shows no "+ Add new film" entry while the search is empty', async () => {
      const element = await render(stubFacade([HEAT, SEVEN]));

      expect(element.querySelector('a.library__add')).toBeNull();
    });

    it('restores the full list once the search is cleared', async () => {
      const element = await render(stubFacade([HEAT, SEVEN]));
      await search(element, 'heat');

      element.querySelector<HTMLButtonElement>('button[aria-label="Clear the search"]')!.click();
      await currentFixture.whenStable();

      expect(element.querySelectorAll('.film__title')).toHaveLength(2);
      expect(element.querySelector('.library__count')?.textContent).toBe('2 films');
    });
  });
});
