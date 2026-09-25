/** Scope switching and the empty states; the numbers themselves are the backend's. */
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { StatsFacade } from '../../domain/stats/facade';
import type { Stats, StatsBlock } from '../../domain/stats/model';
import { Stats as StatsView } from './stats';

const THIS_YEAR = new Date().getFullYear();

function block(watches: number): StatsBlock {
  return {
    watches,
    firstWatches: watches,
    rewatches: 0,
    filmsReleasedThatYear: null,
    distinctFilms: watches,
    minutesWatched: watches * 120,
    averageRating: watches ? 4 : null,
    ratingDistribution: [],
    topGenres: watches ? [{ name: 'Crime', watches, averageRating: 4, score: watches * 4 }] : [],
    topDirectors: watches ? [{ name: 'Michael Mann', watches, averageRating: 4, score: watches * 4 }] : [],
    topFilms: watches ? [{ filmId: 'f1', title: 'Heat', watches, averageRating: 4, score: watches * 4 }] : [],
    buckets: [],
  };
}

function totalBlockWithYearBucket(): StatsBlock {
  return { ...block(5), buckets: [{ label: '2005', count: 3 }] };
}

function render(stats: Stats): HTMLElement {
  TestBed.configureTestingModule({
    imports: [StatsView],
    providers: [
      provideRouter([]),
      {
        provide: StatsFacade,
        useValue: {
          stats: signal(stats),
          isLoading: signal(false),
          error: signal(undefined),
          reload: () => undefined,
          onViewOpened: () => undefined,
        },
      },
    ],
  });
  const fixture = TestBed.createComponent(StatsView);
  fixture.detectChanges();
  return fixture.nativeElement as HTMLElement;
}

describe('Stats view', () => {
  it('preselects the current year', () => {
    const el = render({ total: block(5), years: [{ year: THIS_YEAR, ...block(2) }] });

    // `mat-button-toggle-group` is single-select, so each toggle renders `role="radio"` with
    // `[attr.aria-checked]` bound straight to `checked` — unlike the chip listbox this replaced,
    // there is no `[selectable]` guard that can blank the attribute out.
    expect(el.querySelector('[aria-checked="true"]')?.textContent).toContain(String(THIS_YEAR));
    expect(el.textContent).toContain('Heat');
    expect(el.textContent).toContain('Michael Mann');
    expect(el.textContent).toContain('Crime');
    expect(el.textContent).toContain('2× · 4.0★');
  });

  it('shows the empty state for a year without watches', () => {
    const el = render({ total: block(5), years: [{ year: THIS_YEAR, ...block(0) }] });

    expect(el.textContent).toContain('No watches this year');
  });

  it('shows all time when there are no years', () => {
    const el = render({ total: block(0), years: [] });

    expect(el.querySelector('[aria-checked="true"]')?.textContent).toContain('All time');
    expect(el.textContent).not.toContain('No watches this year');
  });

  it('shortens the all-time chart year labels but keeps the full year in aria-label', () => {
    const el = render({ total: totalBlockWithYearBucket(), years: [] });

    const bar = el.querySelector('.stats__bars li');
    expect(bar?.getAttribute('aria-label')).toBe('2005: 3');
    expect(bar?.querySelector('.stats__bar-label')?.textContent).toBe("'05");
  });
});
