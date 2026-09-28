/** The review list: rows, the Approve-only-with-a-suggestion rule, the create link, dismiss, sync. */
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { MatDialog } from '@angular/material/dialog';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';

import type { LetterboxdEntry } from '../../domain/letterboxd/model';
import { FilmFacade } from '../../domain/film/facade';
import { LetterboxdFacade } from '../../domain/letterboxd/facade';
import { Letterboxd } from './letterboxd';

const SUGGESTED: LetterboxdEntry = {
  id: 'e1',
  filmTitle: 'Heat',
  filmYear: 1995,
  filmUrl: 'https://letterboxd.com/film/heat/',
  watchedDate: '2026-09-20',
  rating: 4.5,
  rewatch: true,
  suggestedFilm: { id: 'f1', title: 'Heat' },
};
const UNMATCHED: LetterboxdEntry = {
  ...SUGGESTED,
  id: 'e2',
  filmTitle: 'Pulse',
  filmYear: 2001,
  rating: null,
  rewatch: false,
  suggestedFilm: null,
};

function stubFacade(entries: readonly LetterboxdEntry[]) {
  return {
    entries: signal(entries),
    isLoading: signal(false),
    loadFailed: signal(false),
    isBusy: signal(false),
    actionError: signal<string | null>(null),
    onViewOpened: vi.fn(),
    reload: vi.fn(),
    assign: vi.fn(),
    dismiss: vi.fn(),
    sync: vi.fn(),
  };
}

async function render(facade: ReturnType<typeof stubFacade>, confirm = true): Promise<HTMLElement> {
  TestBed.configureTestingModule({
    imports: [Letterboxd],
    providers: [
      provideRouter([]),
      { provide: LetterboxdFacade, useValue: facade },
      { provide: FilmFacade, useValue: { films: signal([]) } },
      { provide: MatDialog, useValue: { open: () => ({ afterClosed: () => of(confirm) }) } },
    ],
  });
  const fixture = TestBed.createComponent(Letterboxd);
  await fixture.whenStable();
  return fixture.nativeElement as HTMLElement;
}

function rows(element: HTMLElement): HTMLElement[] {
  return [...element.querySelectorAll<HTMLElement>('.entry')];
}

describe('Letterboxd', () => {
  afterEach(() => TestBed.resetTestingModule());

  it('opens the list on creation', async () => {
    const facade = stubFacade([]);
    await render(facade);

    expect(facade.onViewOpened).toHaveBeenCalled();
  });

  it('shows the empty state with nothing to review', async () => {
    expect((await render(stubFacade([]))).textContent).toContain('Nothing to review');
  });

  it('offers Approve only for an entry with a suggestion', async () => {
    const [suggested, unmatched] = rows(await render(stubFacade([SUGGESTED, UNMATCHED])));

    expect(suggested!.querySelector('.entry__approve')).not.toBeNull();
    expect(unmatched!.querySelector('.entry__approve')).toBeNull();
  });

  it('approves with the suggested film', async () => {
    const facade = stubFacade([SUGGESTED]);
    const [row] = rows(await render(facade));

    row!.querySelector<HTMLButtonElement>('.entry__approve')!.click();

    expect(facade.assign).toHaveBeenCalledWith('e1', 'f1');
  });

  it('links Create film to the prefilled form', async () => {
    const [row] = rows(await render(stubFacade([SUGGESTED])));
    const href = row!.querySelector<HTMLAnchorElement>('.entry__create')!.getAttribute('href')!;
    const params = new URL(href, 'http://x').searchParams;

    expect(href.startsWith('/films/new?')).toBe(true);
    expect(Object.fromEntries(params)).toEqual({
      title: 'Heat',
      year: '1995',
      letterboxdLink: 'https://letterboxd.com/film/heat/',
      watchedOn: '2026-09-20',
      rating: '4.5',
      rewatch: 'true',
    });
  });

  it('dismisses after confirmation', async () => {
    const facade = stubFacade([SUGGESTED]);
    const [row] = rows(await render(facade, true));

    row!.querySelector<HTMLButtonElement>('.entry__dismiss')!.click();

    expect(facade.dismiss).toHaveBeenCalledWith('e1');
  });

  it('keeps the entry when the dismiss is cancelled', async () => {
    const facade = stubFacade([SUGGESTED]);
    const [row] = rows(await render(facade, false));

    row!.querySelector<HTMLButtonElement>('.entry__dismiss')!.click();

    expect(facade.dismiss).not.toHaveBeenCalled();
  });

  it('syncs on demand', async () => {
    const facade = stubFacade([]);
    (await render(facade)).querySelector<HTMLButtonElement>('.letterboxd__sync')!.click();

    expect(facade.sync).toHaveBeenCalled();
  });

  it('shows an unrated entry as unrated', async () => {
    const [row] = rows(await render(stubFacade([UNMATCHED])));

    expect(row!.textContent).toContain('Unrated');
  });
});
