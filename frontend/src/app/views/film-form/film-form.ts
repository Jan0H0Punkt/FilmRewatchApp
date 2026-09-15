/**
 * The Add Film form (`open work/library-view/add-film-via-search.md`, work
 * item 2) — routed at `films/new`. Creates a film together with its
 * mandatory first rating in one `POST /films` (FR-LIB-01..03); reached only
 * through the Library's search (`?title=` prefill) or its Add Film button
 * (§6.1: the view calls facades only, holds no rules of its own).
 */
import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, computed, inject, input, linkedSignal, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { provideNativeDateAdapter } from '@angular/material/core';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { Router, RouterLink } from '@angular/router';

import { FilmFacade } from '../../domain/film/facade';
import type { FilmCreateInput } from '../../domain/film/model';
import { GenreFacade } from '../../domain/genre/facade';
import { TagFacade } from '../../domain/tag/facade';
import { EditableChips } from '../../shared/editable-chips/editable-chips';
import { ratingStarsFor } from '../../shared/rating-stars';

const MIN_RELEASE_YEAR = 1888; // REQ §4.1 — the year of the first film ever made, mirrors the backend bound.
/** The picker's five star positions — reused from `film-detail.ts`'s Add Rating control. */
const STAR_POSITIONS: readonly number[] = [1, 2, 3, 4, 5];

/** Formats a `Date` as `yyyy-MM-dd` in local time — `toISOString` would shift the day across time zones. */
function toIsoDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/** FR-LIB-14: well-formed http(s) URL, nothing more — mirrors the backend's `_validated_url`. */
function isWellFormedHttpUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch {
    return false;
  }
}

/** Surfaces the `core/errors.py` envelope's `message` (e.g. the 409 `DUPLICATE_FILM` collision), falling back otherwise. */
function extractErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof HttpErrorResponse) {
    const body = error.error as { error?: { message?: string } } | null;
    if (body?.error?.message) return body.error.message;
  }
  return fallback;
}

@Component({
  selector: 'app-film-form',
  imports: [
    EditableChips,
    MatButtonModule,
    MatCardModule,
    MatDatepickerModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    RouterLink,
  ],
  // The Watched-on picker needs a date adapter, same as film-detail's Add
  // Rating form; scoped here (not app-wide) so it lands in this lazy chunk.
  providers: [provideNativeDateAdapter()],
  templateUrl: './film-form.html',
  styleUrl: './film-form.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FilmForm {
  private readonly films = inject(FilmFacade);
  private readonly router = inject(Router);

  /** Bound from the `?title=` query param (`withComponentInputBinding()`) — the Library search's prefill. */
  readonly title = input<string>('');

  protected readonly currentYear = new Date().getFullYear();
  protected readonly minReleaseYear = MIN_RELEASE_YEAR;

  /**
   * Seeded from `title`, then freely editable — a `linkedSignal` so a direct
   * `?title=` navigation still prefills it. `?? ''`: `withComponentInputBinding()`
   * leaves the input `undefined` (not the declared default) when the route
   * carries no `title` query param at all, e.g. reached without a search first.
   */
  protected readonly primaryTitle = linkedSignal(() => this.title() ?? '');
  protected readonly originalTitle = signal('');
  protected readonly releaseYear = signal<number | null>(null);
  protected readonly director = signal('');
  protected readonly runtimeMinutes = signal<number | null>(null);
  protected readonly selectedGenres = signal<readonly string[]>([]);
  protected readonly selectedTags = signal<readonly string[]>([]);
  protected readonly posterImage = signal('');
  protected readonly today = new Date();
  protected readonly watchDate = signal<Date | null>(this.today);

  protected readonly tagNames = inject(TagFacade).names;
  protected readonly genreNames = inject(GenreFacade).names;

  // --- Rating picker: same half-star widget as film-detail's Add Rating,
  // but defaulting to 'unrated' rather than requiring an explicit pick —
  // the rating is optional here (doc's field table), so nothing should
  // block submit until the user deliberately rates the watch.
  protected readonly selectedValue = signal<number | 'unrated'>('unrated');
  protected readonly hoverValue = signal<number | null>(null);
  private readonly pickerValue = computed<number>(() => {
    const selected = this.selectedValue();
    return this.hoverValue() ?? (typeof selected === 'number' ? selected : 0);
  });
  protected readonly pickerStars = computed<readonly string[]>(() => ratingStarsFor(this.pickerValue()) ?? []);
  protected readonly starPositions = STAR_POSITIONS;

  protected starLabel(value: number): string {
    return `Rate ${value} star${value === 1 ? '' : 's'}`;
  }

  protected selectStar(value: number): void {
    this.selectedValue.set(value);
  }

  protected selectUnrated(): void {
    this.selectedValue.set('unrated');
  }

  protected onWatchDateChange(value: Date | null): void {
    this.watchDate.set(value);
  }

  protected onReleaseYearChange(value: string): void {
    const parsed = Number(value);
    this.releaseYear.set(value.trim() === '' || Number.isNaN(parsed) ? null : parsed);
  }

  protected onRuntimeChange(value: string): void {
    const parsed = Number(value);
    this.runtimeMinutes.set(value.trim() === '' || Number.isNaN(parsed) ? null : parsed);
  }

  protected readonly posterImageValid = computed(() => {
    const value = this.posterImage().trim();
    return value === '' || isWellFormedHttpUrl(value);
  });

  protected readonly isValid = computed(() => {
    const year = this.releaseYear();
    const runtime = this.runtimeMinutes();
    return (
      this.primaryTitle().trim() !== '' &&
      year !== null &&
      year >= MIN_RELEASE_YEAR &&
      year <= this.currentYear &&
      this.director().trim() !== '' &&
      runtime !== null &&
      runtime >= 1 &&
      this.selectedGenres().length > 0 &&
      this.selectedTags().length > 0 &&
      this.posterImageValid() &&
      this.watchDate() !== null
    );
  });

  protected readonly isSubmitting = signal(false);
  protected readonly submitError = signal<string | null>(null);

  protected onSubmit(event: SubmitEvent): void {
    event.preventDefault();
    this.submit();
  }

  private submit(): void {
    const year = this.releaseYear();
    const runtime = this.runtimeMinutes();
    const watchDate = this.watchDate();
    if (!this.isValid() || year === null || runtime === null || watchDate === null || this.isSubmitting()) return;

    const originalTitle = this.originalTitle().trim();
    const posterImage = this.posterImage().trim();
    const selectedValue = this.selectedValue();
    const payload: FilmCreateInput = {
      primaryTitle: this.primaryTitle().trim(),
      originalTitle: originalTitle === '' ? null : originalTitle,
      releaseYear: year,
      director: this.director().trim(),
      runtimeMinutes: runtime,
      genres: this.selectedGenres(),
      tags: this.selectedTags(),
      posterImage: posterImage === '' ? null : posterImage,
      watchDate: toIsoDate(watchDate),
      rating: selectedValue === 'unrated' ? null : selectedValue,
    };

    this.isSubmitting.set(true);
    this.films.create(payload).subscribe({
      next: () => {
        this.isSubmitting.set(false);
        void this.router.navigateByUrl('/library');
      },
      error: (error: unknown) => {
        this.isSubmitting.set(false);
        this.submitError.set(extractErrorMessage(error, 'The film could not be created.'));
      },
    });
  }
}
