/** The §7.1 card grid and its four states (FR-RW-06/07). */
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { MatDialog } from '@angular/material/dialog';
import { provideRouter } from '@angular/router';

import { RewatchFacade } from '../../domain/rewatch/facade';
import type { RewatchCardVm } from '../../domain/rewatch/model';
import { SettingsFacade } from '../../domain/settings/facade';
import { StatsFacade } from '../../domain/stats/facade';
import type { Stats } from '../../domain/stats/model';
import { LetterboxdDialog } from './letterboxd-dialog';
import { Rewatch } from './rewatch';

const THIS_YEAR = new Date().getFullYear();

/** Stands in for `MatDialog` — `Rewatch` never reads `open()`'s return value. */
function stubMatDialog() {
  return { open: vi.fn() };
}

const HEAT: RewatchCardVm = {
  id: 'f1',
  title: 'Heat',
  year: 1995,
  posterImage: null,
  ratingStars: ['star', 'star', 'star', 'star', 'star_border'],
  ratingLabel: 'Average rating: 4.0 out of 5',
  isFavorite: true,
  owned: true,
  dueLabel: 'Overdue by 5 days',
  letterboxdUrl: null,
};

/**
 * FR-RW-08 inputs for the cap; default to Off/not-loaded so every existing
 * test below (none of which mention the cap) keeps seeing the due-list
 * unfiltered, same as before the setting existed.
 */
interface CapInputs {
  readonly rewatchShare?: number | null;
  readonly stats?: Stats | null;
}

async function render(
  cards: readonly RewatchCardVm[],
  isLoading = false,
  error: unknown = undefined,
  dialog: ReturnType<typeof stubMatDialog> = stubMatDialog(),
  cap: CapInputs = {},
): Promise<HTMLElement> {
  // The favourite test renders twice; without the reset the second
  // `configureTestingModule` throws because a component already exists.
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    imports: [Rewatch],
    providers: [
      provideRouter([]),
      {
        provide: RewatchFacade,
        useValue: {
          cards: signal(cards),
          isLoading: signal(isLoading),
          error: signal(error),
          doneBefore: signal(new Date(2024, 0, 1, 22, 30)),
          reload: (): void => undefined,
          onViewOpened: (): void => undefined,
          setDoneBefore: (): void => undefined,
        },
      },
      {
        provide: SettingsFacade,
        useValue: { rewatchShare: signal(cap.rewatchShare ?? null), onViewOpened: (): void => undefined },
      },
      {
        provide: StatsFacade,
        useValue: { stats: signal(cap.stats ?? null), onViewOpened: (): void => undefined },
      },
      { provide: MatDialog, useValue: dialog },
    ],
  });
  const fixture = TestBed.createComponent(Rewatch);
  await fixture.whenStable();
  return fixture.nativeElement as HTMLElement;
}

function statsWithYear(watches: number, rewatches: number): Stats {
  return {
    total: {
      watches,
      firstWatches: 0,
      rewatches,
      filmsReleasedThatYear: null,
      distinctFilms: 0,
      minutesWatched: 0,
      averageRating: null,
      ratingDistribution: [],
      topGenres: [],
      topDirectors: [],
      topTags: [],
      topFilms: [],
      buckets: [],
    },
    years: [
      {
        year: THIS_YEAR,
        watches,
        firstWatches: 0,
        rewatches,
        filmsReleasedThatYear: null,
        distinctFilms: 0,
        minutesWatched: 0,
        averageRating: null,
        ratingDistribution: [],
        topGenres: [],
        topDirectors: [],
        topTags: [],
        topFilms: [],
        buckets: [],
      },
    ],
  };
}

describe('Rewatch view', () => {
  it('renders a card per due film', async () => {
    const element = await render([HEAT]);

    expect(element.querySelectorAll('.rewatch__card')).toHaveLength(1);
    expect(element.textContent).toContain('Heat');
    expect(element.textContent).toContain('1995');
    expect(element.textContent).toContain('Overdue by 5 days');
  });

  it('links each card to the film detail view', async () => {
    const element = await render([HEAT]);

    expect(element.querySelector('a')?.getAttribute('href')).toBe('/film/f1');
  });

  it('marks a favourite and leaves a non-favourite unmarked', async () => {
    const favourite = await render([HEAT]);
    expect(favourite.querySelector('.rewatch__favorite')).not.toBeNull();

    const plain = await render([{ ...HEAT, isFavorite: false }]);
    expect(plain.querySelector('.rewatch__favorite')).toBeNull();
  });

  it('marks a film owned on disc and leaves an unowned one unmarked', async () => {
    const owned = await render([HEAT]);
    expect(owned.querySelector('.rewatch__owned')).not.toBeNull();

    const plain = await render([{ ...HEAT, owned: false }]);
    expect(plain.querySelector('.rewatch__owned')).toBeNull();
  });

  it('shows a dash rather than empty stars for an unrated film', async () => {
    // FR-RAT-13: five empty stars would read as "rated zero".
    const element = await render([{ ...HEAT, ratingStars: null, ratingLabel: 'Not rated' }]);

    expect(element.querySelector('.rewatch__rating')?.textContent).toContain('—');
  });

  it('shows a loading state while the list is in flight', async () => {
    const element = await render([], true);

    expect(element.querySelector('[role="status"]')).not.toBeNull();
  });

  it('shows an empty state when nothing is due', async () => {
    // FR-RW-06: an empty due-list is a normal answer, not an error.
    const element = await render([]);

    expect(element.textContent).toContain('Nothing due right now');
    expect(element.querySelector('[role="alert"]')).toBeNull();
  });

  it('shows the "done watching by" time filter', async () => {
    const element = await render([HEAT]);

    expect(element.textContent).toContain('Done watching by');
    expect(element.querySelector('mat-timepicker-toggle')).not.toBeNull();
  });

  it('states how many films are due', async () => {
    const element = await render([HEAT, { ...HEAT, id: 'f2', title: 'Se7en' }]);

    expect(element.querySelector('.rewatch__count')?.textContent).toBe('2 films due');
  });

  it('says "film" rather than "films" for a single due film', async () => {
    const element = await render([HEAT]);

    expect(element.querySelector('.rewatch__count')?.textContent).toBe('1 film due');
  });

  it('states no count when nothing is due, since the empty state already says so', async () => {
    const element = await render([]);

    expect(element.querySelector('.rewatch__count')).toBeNull();
  });

  it('shows a non-blocking error without hiding the cards it already has', async () => {
    // FR-RW-07: the error is additive — the last successful run stays on screen.
    const element = await render([HEAT], false, new Error('boom'));

    expect(element.querySelector('[role="alert"]')).not.toBeNull();
    expect(element.querySelectorAll('.rewatch__card')).toHaveLength(1);
  });

  describe('rewatch-share cap (FR-RW-08, §Cap)', () => {
    const SEVEN: RewatchCardVm = { ...HEAT, id: 'f2', title: 'Se7en' };
    const PULP: RewatchCardVm = { ...HEAT, id: 'f3', title: 'Pulp Fiction' };

    it('shows the full list when the share is Off', async () => {
      const element = await render([HEAT, SEVEN, PULP], false, undefined, stubMatDialog(), {
        rewatchShare: null,
        stats: statsWithYear(2, 0),
      });

      expect(element.querySelectorAll('.rewatch__card')).toHaveLength(3);
      expect(element.querySelector('.rewatch__count')?.textContent).toBe('3 films due');
    });

    it('shows the full list, no cap, when stats failed to load (fails open)', async () => {
      const element = await render([HEAT, SEVEN, PULP], false, undefined, stubMatDialog(), {
        rewatchShare: 50,
        stats: null,
      });

      expect(element.querySelectorAll('.rewatch__card')).toHaveLength(3);
    });

    it("shows only the prefix the cap allows, in the algorithm's order, with the note above the list", async () => {
      // share 50%, 2 watches and 0 rewatches this year -> k = 2 (see rewatch-cap.spec.ts).
      const element = await render([HEAT, SEVEN, PULP], false, undefined, stubMatDialog(), {
        rewatchShare: 50,
        stats: statsWithYear(2, 0),
      });

      const cards = element.querySelectorAll('.rewatch__card');
      expect(cards).toHaveLength(2);
      expect(element.textContent).toContain('Heat');
      expect(element.textContent).toContain('Se7en');
      expect(element.textContent).not.toContain('Pulp Fiction');
      expect(element.querySelector('.rewatch__count')?.textContent).toBe(
        'Showing 2 of 3 due films · 50% rewatch target',
      );
    });

    it('replaces the empty state with the note when the cap is zero', async () => {
      const element = await render([HEAT, SEVEN], false, undefined, stubMatDialog(), {
        rewatchShare: 0,
        stats: statsWithYear(5, 1),
      });

      expect(element.querySelectorAll('.rewatch__card')).toHaveLength(0);
      expect(element.textContent).toContain('Showing 0 of 2 due films · 0% rewatch target');
      expect(element.textContent).not.toContain('Nothing due right now');
    });

    it('shows no note when the cap hides nothing', async () => {
      const element = await render([HEAT], false, undefined, stubMatDialog(), {
        rewatchShare: 90,
        stats: statsWithYear(100, 0),
      });

      expect(element.querySelector('.rewatch__count')?.textContent).toBe('1 film due');
    });
  });

  describe('Letterboxd title icon (§7.1)', () => {
    it('is shown even when the film has no link yet', async () => {
      const element = await render([HEAT]); // HEAT.letterboxdUrl is null

      const icon = element.querySelector('.rewatch__letterboxd');
      expect(icon).not.toBeNull();
      // Not nested inside the card's stretched link (rewatch.html) — it stays
      // independently clickable via CSS stacking, not event plumbing.
      expect(element.querySelector('a')?.contains(icon)).toBe(false);
    });

    it('opens the link directly when one is saved', async () => {
      const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null);
      const element = await render([{ ...HEAT, letterboxdUrl: 'https://boxd.it/aaaa' }]);

      element.querySelector<HTMLButtonElement>('.rewatch__letterboxd')!.click();

      expect(openSpy).toHaveBeenCalledWith('https://boxd.it/aaaa', '_blank', 'noopener,noreferrer');
    });

    it('opens the add-link dialog when none is saved', async () => {
      const dialog = stubMatDialog();
      const element = await render([HEAT], false, undefined, dialog);

      element.querySelector<HTMLButtonElement>('.rewatch__letterboxd')!.click();

      expect(dialog.open).toHaveBeenCalledWith(LetterboxdDialog, { data: { filmId: HEAT.id } });
    });
  });
});
