/**
 * Film Detail view: loading/error/loaded states, the ViewModel shaping
 * (REQ §7.3 Section A), and the rating-history actions (phase 2, Section B).
 */
import { HttpErrorResponse } from '@angular/common/http';
import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideNativeDateAdapter } from '@angular/material/core';
import { MatDialog } from '@angular/material/dialog';
import { Router, provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';

import { FilmFacade } from '../../domain/film/facade';
import type { FilmDetail as FilmDetailModel } from '../../domain/film/model';
import { RatingFacade } from '../../domain/rating/facade';
import type { ConfirmDialogData } from '../../shared/confirm-dialog/confirm-dialog';
import { FilmDetail } from './film-detail';

const HEAT: FilmDetailModel = {
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
  titles: [
    { value: 'Heat', isPrimary: true, isOriginal: false },
    { value: 'ヒート', isPrimary: false, isOriginal: true },
  ],
  delayDays: 0,
  ratingHistory: [
    { id: 'r2', value: 4.5, watchDate: '2024-02-01', createdAt: '2024-02-01T20:00:00Z' },
    { id: 'r1', value: null, watchDate: '2024-01-01', createdAt: '2024-01-01T20:00:00Z' },
  ],
  createdAt: '2024-01-01T10:00:00Z',
  updatedAt: '2024-01-02T10:00:00Z',
};

/** Stands in for `FilmFacade` so the view is tested without HTTP. */
function stubFilmFacade(
  detail: FilmDetailModel | null,
  isLoading = false,
  error: unknown = undefined,
  notFound = false,
) {
  return {
    detail: signal(detail),
    detailIsLoading: signal(isLoading),
    detailError: signal(error),
    detailNotFound: signal(notFound),
    select: vi.fn(),
    reload: vi.fn(),
    update: vi.fn().mockReturnValue(of(undefined)),
    remove: vi.fn().mockReturnValue(of(undefined)),
  };
}

/** Stands in for `RatingFacade` — the facade under test is `FilmDetail`, not this one. */
function stubRatingFacade() {
  return {
    add: vi.fn().mockReturnValue(of(undefined)),
    remove: vi.fn().mockReturnValue(of({ ratingId: 'r1', filmId: 'f1', filmDeleted: false })),
  };
}

/** Stands in for `MatDialog` — resolves `afterClosed()` with `confirmed` without rendering a real overlay. */
function stubMatDialog(confirmed: boolean) {
  return { open: vi.fn().mockReturnValue({ afterClosed: () => of(confirmed) }) };
}

/** The most recently created fixture — lets a test await a later change after its own interaction. */
let currentFixture: ComponentFixture<FilmDetail>;

async function render(
  filmFacade: ReturnType<typeof stubFilmFacade>,
  ratingFacade: ReturnType<typeof stubRatingFacade> = stubRatingFacade(),
  dialog: ReturnType<typeof stubMatDialog> | undefined = undefined,
): Promise<HTMLElement> {
  TestBed.configureTestingModule({
    imports: [FilmDetail],
    providers: [
      provideRouter([]),
      provideNativeDateAdapter(),
      { provide: FilmFacade, useValue: filmFacade },
      { provide: RatingFacade, useValue: ratingFacade },
      ...(dialog ? [{ provide: MatDialog, useValue: dialog }] : []),
    ],
  });
  currentFixture = TestBed.createComponent(FilmDetail);
  currentFixture.componentRef.setInput('id', HEAT.id);
  await currentFixture.whenStable();
  return currentFixture.nativeElement as HTMLElement;
}

/** Awaits the pending change-detection round after an interaction outside `render()`. */
async function settle(): Promise<void> {
  await currentFixture.whenStable();
}

/** The five picker glyphs in position order — 'star' / 'star_half' / 'star_border'. */
function pickerIcons(element: HTMLElement): string[] {
  return [...element.querySelectorAll('.rating-form__star mat-icon')].map((icon) => icon.textContent?.trim() ?? '');
}

/** One of the picker's ten half-star hit targets, found by its distinct aria-label. */
function starHalf(element: HTMLElement, value: number): HTMLButtonElement | null {
  return element.querySelector<HTMLButtonElement>(
    `.rating-form__star-half[aria-label="Rate ${value} star${value === 1 ? '' : 's'}"]`,
  );
}

describe('FilmDetail', () => {
  afterEach(() => TestBed.resetTestingModule());

  it('renders a loading state', async () => {
    const element = await render(stubFilmFacade(null, true));

    expect(element.querySelector('[role="status"]')?.textContent).toContain('Loading');
  });

  it('renders an error state and retries through the facade', async () => {
    const facade = stubFilmFacade(null, false, new Error('offline'));
    const element = await render(facade);

    const button = element.querySelector('[role="alert"] button');
    expect(button).not.toBeNull();
    (button as HTMLButtonElement).click();
    expect(facade.reload).toHaveBeenCalledOnce();
  });

  it('renders a not-found state with a link back to the library', async () => {
    // The fallback fetch settled with a 404 — distinct from loading and error.
    const element = await render(stubFilmFacade(null, false, undefined, true));

    expect(element.querySelector('[role="status"]')).toBeNull();
    expect(element.querySelector('[role="alert"]')).toBeNull();
    expect(element.textContent).toContain('could not be found');
    const link = element.querySelector('.film-detail__state a[href="/library"]');
    expect(link).not.toBeNull();
  });

  it('renders the primary title, subtitle, genres and tags', async () => {
    const element = await render(stubFilmFacade(HEAT));

    expect(element.querySelector('.film-detail__title')?.textContent).toContain('Heat');
    expect(element.querySelector('.film-detail__subtitle')?.textContent).toBe('1995 · Michael Mann · 170 min');
    const genres = [...element.querySelectorAll('.film-detail__genre')].map((el) => el.textContent);
    expect(genres).toEqual(['Crime', 'Thriller']);
  });

  it('lists alternative titles beneath the primary one, marking the original', async () => {
    const element = await render(stubFilmFacade(HEAT));

    const altTitles = element.querySelector('.film-detail__alt-titles');
    expect(altTitles?.textContent).toContain('ヒート');
    expect(altTitles?.textContent).toContain('(original)');
  });

  it('shows a dash instead of stars for a film the user chose not to rate', async () => {
    // FR-RAT-13: unrated is not zero stars — it has to read as "no rating given".
    const element = await render(stubFilmFacade({ ...HEAT, averageRating: null }));

    const rating = element.querySelector('.film-detail__rating');
    expect(rating?.querySelectorAll('mat-icon')).toHaveLength(0);
    expect(rating?.textContent?.trim()).toBe('—');
    expect(rating?.getAttribute('aria-label')).toBe('Not rated');
  });

  it('renders the numeric average rating next to the stars for a rated film', async () => {
    const element = await render(stubFilmFacade(HEAT));

    const rating = element.querySelector('.film-detail__rating');
    const ratingText = rating?.querySelector('.film-detail__rating-text');
    expect(ratingText?.textContent).toBe('4.0');
    expect(rating?.querySelectorAll('mat-icon')).toHaveLength(5);
  });

  it('does not render a numeric average for an unrated film, only the em-dash', async () => {
    const element = await render(stubFilmFacade({ ...HEAT, averageRating: null }));

    const rating = element.querySelector('.film-detail__rating');
    const ratingText = rating?.querySelector('.film-detail__rating-text');
    expect(ratingText).toBeNull();
    expect(rating?.textContent?.trim()).toBe('—');
  });

  it('selects the film through the facade using the routed id', async () => {
    const facade = stubFilmFacade(HEAT);
    await render(facade);

    expect(facade.select).toHaveBeenCalledWith(HEAT.id);
  });

  it('points the back control at the library route', async () => {
    const element = await render(stubFilmFacade(HEAT));

    const back = element.querySelector('a[aria-label="Back to library"]');
    expect(back?.getAttribute('href')).toBe('/library');
  });

  describe('rating history (Section B)', () => {
    it('lists the rating history newest-first, without re-sorting', async () => {
      const element = await render(stubFilmFacade(HEAT));

      const items = [...element.querySelectorAll('.rating-history__item')];
      expect(items).toHaveLength(2);
      expect(items[0]?.textContent).toContain('Watched Feb 1, 2024');
      expect(items[1]?.textContent).toContain('Watched Jan 1, 2024');
    });

    it('shows "Not rated" for a null history entry instead of zero stars', async () => {
      const element = await render(stubFilmFacade(HEAT));

      const unratedItem = [...element.querySelectorAll('.rating-history__item')][1];
      expect(unratedItem?.querySelector('.rating-history__value')?.textContent?.trim()).toBe('Not rated');
    });

    it('requires confirmation before deleting a rating', async () => {
      const ratingFacade = stubRatingFacade();
      const element = await render(stubFilmFacade(HEAT), ratingFacade, stubMatDialog(false));

      const deleteButton = element.querySelector<HTMLButtonElement>(
        '.rating-history__item button[aria-label="Delete this rating entry"]',
      );
      deleteButton?.click();

      expect(ratingFacade.remove).not.toHaveBeenCalled();
    });

    it('deletes through the facade once confirmed', async () => {
      const ratingFacade = stubRatingFacade();
      const element = await render(stubFilmFacade(HEAT), ratingFacade, stubMatDialog(true));

      const deleteButton = element.querySelector<HTMLButtonElement>(
        '.rating-history__item button[aria-label="Delete this rating entry"]',
      );
      deleteButton?.click();

      expect(ratingFacade.remove).toHaveBeenCalledWith('r2');
    });

    it('states that the whole film will be deleted when its only rating is removed', async () => {
      // FR-RAT-07: the dialog must state the known outcome, not hedge with "if".
      const onlyRating: FilmDetailModel = {
        ...HEAT,
        ratingHistory: [HEAT.ratingHistory[0]!],
      };
      const dialog = stubMatDialog(false);
      const element = await render(stubFilmFacade(onlyRating), stubRatingFacade(), dialog);

      const deleteButton = element.querySelector<HTMLButtonElement>(
        '.rating-history__item button[aria-label="Delete this rating entry"]',
      );
      deleteButton?.click();

      const data = dialog.open.mock.calls[0]?.[1]?.data as ConfirmDialogData;
      expect(data.message).toContain('Heat');
      expect(data.message).toContain('whole film');
      expect(data.confirmLabel).toBe('Delete film');
    });

    it('navigates to the Library when deleting the last rating deletes the film', async () => {
      const ratingFacade = stubRatingFacade();
      ratingFacade.remove.mockReturnValue(of({ ratingId: 'r2', filmId: 'f1', filmDeleted: true }));
      const element = await render(stubFilmFacade(HEAT), ratingFacade, stubMatDialog(true));
      const router = TestBed.inject(Router);
      const navigateSpy = vi.spyOn(router, 'navigateByUrl');

      const deleteButton = element.querySelector<HTMLButtonElement>(
        '.rating-history__item button[aria-label="Delete this rating entry"]',
      );
      deleteButton?.click();

      expect(navigateSpy).toHaveBeenCalledWith('/library');
    });

    it('starts with no rating choice made and disables submit until one is picked', async () => {
      // FR-RAT-12: "Don't rate this" must not be a pre-selected default.
      const element = await render(stubFilmFacade(HEAT));

      const unratedButton = element.querySelector<HTMLButtonElement>('.rating-form__unrated');
      const starHalves = [...element.querySelectorAll<HTMLButtonElement>('.rating-form__star-half')];
      const starIcons = [...element.querySelectorAll('.rating-form__star')];
      const submitButton = element.querySelector<HTMLButtonElement>('.rating-form button[type="submit"]');

      expect(unratedButton?.getAttribute('aria-pressed')).toBe('false');
      expect(unratedButton?.classList.contains('rating-form__unrated--active')).toBe(false);
      expect(starHalves).toHaveLength(10);
      expect(starHalves.every((button) => button.getAttribute('aria-pressed') === 'false')).toBe(true);
      expect(starIcons.every((icon) => !icon.classList.contains('rating-form__star--filled'))).toBe(true);
      expect(pickerIcons(element)).toEqual(['star_border', 'star_border', 'star_border', 'star_border', 'star_border']);
      expect(submitButton?.disabled).toBe(true);

      unratedButton?.click();
      await settle();

      expect(submitButton?.disabled).toBe(false);
    });

    it('previews the value a click would give when hovering the left half of a star', async () => {
      const element = await render(stubFilmFacade(HEAT));

      starHalf(element, 2.5)?.dispatchEvent(new Event('mouseenter'));
      await settle();

      expect(pickerIcons(element)).toEqual(['star', 'star', 'star_half', 'star_border', 'star_border']);
    });

    it('previews the full star when hovering the right half of a star', async () => {
      const element = await render(stubFilmFacade(HEAT));

      starHalf(element, 3)?.dispatchEvent(new Event('mouseenter'));
      await settle();

      expect(pickerIcons(element)).toEqual(['star', 'star', 'star', 'star_border', 'star_border']);
    });

    it('previews the same value on keyboard focus as on mouse hover', async () => {
      const element = await render(stubFilmFacade(HEAT));

      starHalf(element, 2.5)?.dispatchEvent(new Event('focus'));
      await settle();

      expect(pickerIcons(element)).toEqual(['star', 'star', 'star_half', 'star_border', 'star_border']);
    });

    it('restores the selected value once the pointer leaves the star row', async () => {
      const element = await render(stubFilmFacade(HEAT));

      starHalf(element, 2)?.click();
      await settle();
      starHalf(element, 3.5)?.dispatchEvent(new Event('mouseenter'));
      await settle();
      expect(pickerIcons(element)).toEqual(['star', 'star', 'star', 'star_half', 'star_border']);

      element.querySelector('.rating-form__stars')?.dispatchEvent(new Event('mouseleave'));
      await settle();

      expect(pickerIcons(element)).toEqual(['star', 'star', 'star_border', 'star_border', 'star_border']);
    });

    it('sends an explicit null value when "Don\'t rate this" is chosen', async () => {
      const ratingFacade = stubRatingFacade();
      const element = await render(stubFilmFacade(HEAT), ratingFacade);

      element.querySelector<HTMLButtonElement>('.rating-form__unrated')?.click();
      await settle();
      const form = element.querySelector('form.rating-form');
      form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      await settle();

      expect(ratingFacade.add).toHaveBeenCalledWith(HEAT.id, expect.objectContaining({ value: null }));
    });

    it('surfaces the add-rating error message from the error envelope', async () => {
      const ratingFacade = stubRatingFacade();
      ratingFacade.add.mockReturnValue(
        throwError(
          () =>
            new HttpErrorResponse({
              status: 422,
              error: { error: { code: 'FUTURE_WATCH_DATE', message: 'The watch date cannot be in the future.' } },
            }),
        ),
      );
      const element = await render(stubFilmFacade(HEAT), ratingFacade);

      // A choice is required before submit does anything (FR-RAT-12).
      element.querySelector<HTMLButtonElement>('.rating-form__unrated')?.click();
      await settle();

      // jsdom doesn't implement `HTMLFormElement.requestSubmit`, which a real
      // click on the submit button would trigger — dispatch the native
      // `submit` event `(ngSubmit)` listens for instead.
      const form = element.querySelector('form.rating-form');
      form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      await settle();

      expect(element.querySelector('.rating-form__error')?.textContent).toContain(
        'The watch date cannot be in the future.',
      );
    });
  });

  describe('film-level actions (Section A, phase 3)', () => {
    it('sends only `isFavorite` when the favourite toggle is clicked', async () => {
      const filmFacade = stubFilmFacade(HEAT);
      const element = await render(filmFacade);

      element.querySelector<HTMLButtonElement>('[aria-label="Remove from favourites"]')?.click();

      expect(filmFacade.update).toHaveBeenCalledWith(HEAT.id, { isFavorite: false });
    });

    it('reflects the current favourite state as `aria-pressed`', async () => {
      const element = await render(stubFilmFacade(HEAT));

      const button = element.querySelector('[aria-label="Remove from favourites"]');
      expect(button?.getAttribute('aria-pressed')).toBe('true');
    });

    it('debounces the rewatch delay input, sending only the final value once', async () => {
      // A number input's spinner arrows fire a native `change` per click —
      // two rapid changes must still yield exactly one PATCH.
      const filmFacade = stubFilmFacade(HEAT);
      const element = await render(filmFacade);
      const input = element.querySelector<HTMLInputElement>('.film-detail__delay input')!;

      vi.useFakeTimers();
      input.value = '14';
      input.dispatchEvent(new Event('change', { bubbles: true }));
      input.value = '15';
      input.dispatchEvent(new Event('change', { bubbles: true }));
      expect(filmFacade.update).not.toHaveBeenCalled();

      vi.advanceTimersByTime(500);
      vi.useRealTimers();

      expect(filmFacade.update).toHaveBeenCalledOnce();
      expect(filmFacade.update).toHaveBeenCalledWith(HEAT.id, { delayDays: 15 });
    });

    it('does not send a request when the delay field is committed unchanged', async () => {
      const filmFacade = stubFilmFacade(HEAT);
      const element = await render(filmFacade);
      const input = element.querySelector<HTMLInputElement>('.film-detail__delay input')!;

      vi.useFakeTimers();
      input.value = String(HEAT.delayDays);
      input.dispatchEvent(new Event('change', { bubbles: true }));
      vi.advanceTimersByTime(500);
      vi.useRealTimers();

      expect(filmFacade.update).not.toHaveBeenCalled();
    });

    it('requires confirmation before deleting the film', async () => {
      const filmFacade = stubFilmFacade(HEAT);
      const element = await render(filmFacade, stubRatingFacade(), stubMatDialog(false));

      const deleteButton = [...element.querySelectorAll<HTMLButtonElement>('.film-detail__body button')].find(
        (button) => button.textContent?.includes('Delete film'),
      );
      deleteButton?.click();

      expect(filmFacade.remove).not.toHaveBeenCalled();
    });

    it('deletes the film and navigates to the Library once confirmed', async () => {
      const filmFacade = stubFilmFacade(HEAT);
      const element = await render(filmFacade, stubRatingFacade(), stubMatDialog(true));
      const router = TestBed.inject(Router);
      const navigateSpy = vi.spyOn(router, 'navigateByUrl');

      const deleteButton = [...element.querySelectorAll<HTMLButtonElement>('.film-detail__body button')].find(
        (button) => button.textContent?.includes('Delete film'),
      );
      deleteButton?.click();
      await settle();

      expect(filmFacade.remove).toHaveBeenCalledWith(HEAT.id);
      expect(navigateSpy).toHaveBeenCalledWith('/library');
    });

    it('states plainly that the film and its rating history are both deleted', async () => {
      const dialog = stubMatDialog(false);
      const element = await render(stubFilmFacade(HEAT), stubRatingFacade(), dialog);

      const deleteButton = [...element.querySelectorAll<HTMLButtonElement>('.film-detail__body button')].find(
        (button) => button.textContent?.includes('Delete film'),
      );
      deleteButton?.click();

      const data = dialog.open.mock.calls[0]?.[1]?.data as ConfirmDialogData;
      expect(data.message).toContain('Heat');
      expect(data.message).toContain('rating history');
      expect(data.message).toContain('cannot be undone');
    });
  });
});
