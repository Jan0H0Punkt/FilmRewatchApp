/**
 * The Library view (REQ §7.2) — the whole film library as a result list,
 * narrowable by a title search (FR-SF-01). The Add Film action is the rest
 * of §7.2 and is not built yet. Per §6.1 the view calls the facade only and
 * holds no rules — the ViewModel shaping (the parts of a film this list
 * actually prints) and the filtering (`filters.ts`) both live here.
 */
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
  viewChild,
  type ElementRef,
} from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { RouterLink } from '@angular/router';

import { ClockService } from '../../core/clock';
import { FilmFacade } from '../../domain/film/facade';
import { filterFilms, hasActiveCriteria, NO_CRITERIA, type LibraryCriteria } from './filters';

/** One row of the result list (§7.2 "Film Result Item"). */
interface FilmRowVm {
  readonly id: string;
  readonly title: string;
  readonly posterImage: string | null;
  /** Year, director, and runtime as the one subtitle line the row prints. */
  readonly subtitle: string;
  readonly genres: readonly string[];
  readonly tags: readonly string[];
  /**
   * Five Material star icon names ('star' | 'star_half' | 'star_border'), rounded
   * to the nearest half star — `null` for a film with no average (FR-RAT-11), which
   * the row prints as a dash instead (FR-RAT-13). Five empty stars would read as
   * "rated zero", which is the opposite of "deliberately not rated".
   */
  readonly ratingStars: readonly string[] | null;
  readonly ratingLabel: string;
  readonly isFavorite: boolean;
  /** Rough clock time the film would end if watching started now, rounded up to the next quarter hour. */
  readonly endTime: string;
}

const QUARTER_HOUR_MS = 15 * 60_000;
const timeFormat = new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' });

function endTimeFrom(now: number, runtimeMinutes: number): string {
  const end = now + runtimeMinutes * 60_000;
  const rounded = Math.ceil(end / QUARTER_HOUR_MS) * QUARTER_HOUR_MS;
  return timeFormat.format(new Date(rounded));
}

/** Rounds to the nearest half star and maps each of the 5 positions to a Material star icon. */
function ratingStars(rating: number | null): readonly string[] | null {
  if (rating === null) return null;
  const rounded = Math.round(rating * 2) / 2;
  return Array.from({ length: 5 }, (_, index) => {
    const position = index + 1;
    if (rounded >= position) return 'star';
    if (position - rounded === 0.5) return 'star_half';
    return 'star_border';
  });
}

@Component({
  selector: 'app-library',
  imports: [
    MatButtonModule,
    MatCardModule,
    MatChipsModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    RouterLink,
  ],
  templateUrl: './library.html',
  styleUrl: './library.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Library {
  private readonly films = inject(FilmFacade);
  private readonly clock = inject(ClockService);

  protected readonly isLoading = this.films.isLoading;
  protected readonly error = this.films.error;

  private readonly searchInput = viewChild<ElementRef<HTMLInputElement>>('search');
  private hasFocusedSearch = false;

  constructor() {
    // The search field is the view's entry point, so it takes focus on arrival.
    // It is only in the DOM once the library has loaded and turned out non-empty,
    // which is why this waits for the query to fill rather than firing on first
    // render — and why it fires exactly once, not on every later re-render.
    effect(() => {
      const input = this.searchInput();
      if (input === undefined || this.hasFocusedSearch) return;
      this.hasFocusedSearch = true;
      input.nativeElement.focus();
    });
  }

  protected readonly criteria = signal<LibraryCriteria>(NO_CRITERIA);
  private readonly matches = computed(() => filterFilms(this.films.films(), this.criteria()));
  protected readonly isFiltered = computed(() => hasActiveCriteria(this.criteria()));
  protected readonly totalCount = computed(() => this.films.films().length);
  /** FR-SF-05: the result count stays on screen at all times, in one of two shapes. */
  protected readonly countLabel = computed<string>(() => {
    const total = this.totalCount();
    const noun = `film${total === 1 ? '' : 's'}`;
    return this.isFiltered() ? `${this.matches().length} of ${total} ${noun}` : `${total} ${noun}`;
  });
  protected setTitle(title: string): void {
    this.criteria.update((criteria) => ({ ...criteria, title }));
  }

  /** Resets the search and returns focus to the input, so clearing does not cost the user their place. */
  protected clear(input: HTMLInputElement): void {
    this.criteria.set(NO_CRITERIA);
    input.focus();
  }

  protected readonly rows = computed<readonly FilmRowVm[]>(() => {
    const now = this.clock.now();
    return this.matches().map((film) => ({
      id: film.id,
      title: film.primaryTitle,
      posterImage: film.posterImage,
      subtitle: [String(film.releaseYear), film.director, `${film.runtimeMinutes} min`].join(' • '),
      genres: film.genres,
      tags: film.tags,
      ratingStars: ratingStars(film.averageRating),
      ratingLabel:
        film.averageRating === null ? 'Not rated' : `Average rating: ${film.averageRating.toFixed(1)} out of 5`,
      isFavorite: film.isFavorite,
      endTime: endTimeFrom(now, film.runtimeMinutes),
    }));
  });

  protected reload(): void {
    this.films.reload();
  }
}
