/**
 * The Library view (REQ §7.2) — the whole film library as a result list,
 * narrowable by a title search (FR-SF-01), plus the Add Film action
 * (FR-LIB-05): the search field
 * doubles as the add entry point (labelled "Search or Add Film") and only
 * ever routes to `films/new` when a search yields no match — never opens a
 * form itself, so there is exactly one path into the create flow. Per §6.1
 * the view calls the facade only and holds no rules — the ViewModel shaping
 * (the parts of a film this list actually prints) and the filtering
 * (`filters.ts`) both live here. Rows render in pages of 50, appending
 * another page as the user scrolls near the end.
 */
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  linkedSignal,
  signal,
  viewChild,
  ElementRef,
} from '@angular/core';
import { ScrollDispatcher } from '@angular/cdk/scrolling';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatTooltipModule } from '@angular/material/tooltip';
import { RouterLink } from '@angular/router';

import { ClockService } from '../../core/clock';
import { ScrollMemoryService } from '../../core/scroll-memory';
import { FilmFacade } from '../../domain/film/facade';
import { ratingLabelFor, ratingStarsFor } from '../../shared/rating-stars';
import { ScrollToTopFab } from '../../shared/scroll-to-top-fab/scroll-to-top-fab';
import { TruncatedTooltipDirective } from '../../shared/truncated-tooltip';
import { filterFilms, hasActiveCriteria, NO_CRITERIA, type LibraryCriteria } from './filters';

/** Key under which this view's scroll offset is remembered (`ScrollMemoryService`). */
const SCROLL_KEY = 'library';

/**
 * Rows rendered initially, and appended per load-more. Paged rather than
 * `cdk-virtual-scroll-viewport`: row heights vary (the genre and tag chip sets
 * are optional and wrap), and CDK's only stable scroll strategy needs a fixed one.
 */
const PAGE_SIZE = 50;

/** Load the next page once the scroll position is this close to the bottom. */
const NEAR_END_PX = 1500;

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
  readonly owned: boolean;
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

@Component({
  selector: 'app-library',
  imports: [
    MatButtonModule,
    MatCardModule,
    MatChipsModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatTooltipModule,
    RouterLink,
    ScrollToTopFab,
    TruncatedTooltipDirective,
  ],
  templateUrl: './library.html',
  styleUrl: './library.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Library {
  private readonly films = inject(FilmFacade);
  private readonly clock = inject(ClockService);
  private readonly scrollMemory = inject(ScrollMemoryService);

  protected readonly isLoading = this.films.isLoading;
  protected readonly error = this.films.error;

  private readonly searchInput = viewChild<ElementRef<HTMLInputElement>>('search');
  private readonly body = viewChild<ElementRef<HTMLElement>>('body');
  private hasFocusedSearch = false;

  /**
   * Up/Down roves focus across the search field, the "Add new film" link, and the
   * result rows — all plain focusable elements already in tab order, so this only
   * ever moves focus among `.library__nav-target`s, never changes tabindex.
   */
  protected onNavKeydown(event: KeyboardEvent): void {
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
    const targets = [...(this.body()?.nativeElement.querySelectorAll<HTMLElement>('.library__nav-target') ?? [])];
    const current = targets.indexOf(document.activeElement as HTMLElement);
    if (current === -1) return;
    event.preventDefault();
    const next = current + (event.key === 'ArrowDown' ? 1 : -1);
    targets[next]?.focus();
  }

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

    this.scrollMemory.remember(SCROLL_KEY, this.isLoading, this.renderLimit);

    // Same containment filter as the scroll-to-top FAB: only the shell's content panel counts.
    const host = inject<ElementRef<HTMLElement>>(ElementRef).nativeElement;
    inject(ScrollDispatcher)
      .scrolled()
      .pipe(takeUntilDestroyed())
      .subscribe((target) => {
        const scroller = target?.getElementRef().nativeElement;
        if (!scroller?.contains(host)) return;
        const nearEnd = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < NEAR_END_PX;
        if (nearEnd && this.renderLimit() < this.matches().length) this.renderLimit.update((n) => n + PAGE_SIZE);
      });
  }

  protected readonly criteria = signal<LibraryCriteria>(NO_CRITERIA);
  /** How many matches are rendered; resets on a new search, not when the film list reloads. */
  protected readonly renderLimit = linkedSignal({ source: this.criteria, computation: () => PAGE_SIZE });
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
    return this.matches()
      .slice(0, this.renderLimit())
      .map((film) => ({
        id: film.id,
        title: film.primaryTitle,
        posterImage: film.posterImage,
        subtitle: [String(film.releaseYear), film.director, `${film.runtimeMinutes} min`].join(' • '),
        genres: film.genres,
        tags: film.tags,
        ratingStars: ratingStarsFor(film.averageRating),
        ratingLabel: ratingLabelFor(film.averageRating),
        isFavorite: film.isFavorite,
        owned: film.owned,
        endTime: endTimeFrom(now, film.runtimeMinutes),
      }));
  });

  protected reload(): void {
    this.films.reload();
  }
}
