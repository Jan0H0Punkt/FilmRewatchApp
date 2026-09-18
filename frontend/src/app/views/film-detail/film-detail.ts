/**
 * The Film Detail view (REQ §7.3) — phase 1 of
 * `open work/library-view/film-detail-view.md` (Section A, read-only
 * metadata), phase 2 (Section B, rating history actions), phase 3
 * (Section A's favourite toggle, rewatch delay, and Delete Film), and the
 * inline tag and genre editing that reversed that plan's deliberate cut #1.
 *
 * The Edit form (phase 4, `films/:id/edit`) is a separate plan item and is
 * not built here — there is deliberately no Edit control on this view yet.
 */
import { HttpErrorResponse } from '@angular/common/http';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  ElementRef,
  inject,
  input,
  signal,
  viewChild,
  type WritableSignal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { provideNativeDateAdapter } from '@angular/material/core';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatDialog } from '@angular/material/dialog';
import { MatDividerModule } from '@angular/material/divider';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatListModule } from '@angular/material/list';
import { Router, RouterLink } from '@angular/router';
import { Subject, debounceTime } from 'rxjs';

import { NavigationHistoryService } from '../../core/navigation-history';
import { FilmFacade } from '../../domain/film/facade';
import { GenreFacade } from '../../domain/genre/facade';
import type { FilmDetail as FilmDetailModel, FilmPatch, RatingHistoryEntry } from '../../domain/film/model';
import { RatingFacade } from '../../domain/rating/facade';
import type { RatingDraft } from '../../domain/rating/model';
import { TagFacade } from '../../domain/tag/facade';
import { ConfirmDialog, type ConfirmDialogData } from '../../shared/confirm-dialog/confirm-dialog';
import { EditableChips } from '../../shared/editable-chips/editable-chips';

/** One alternative title beneath the primary one (REQ §4.1 Title object). */
interface AlternativeTitleVm {
  readonly value: string;
  readonly isOriginal: boolean;
}

/** One rating-history row (§7.3 Section B). */
interface RatingHistoryVm {
  readonly id: string;
  /** Five Material star icon names, or `null` for the FR-RAT-13 "Not rated" placeholder. */
  readonly stars: readonly string[] | null;
  readonly watchDate: string;
  readonly createdAt: string;
}

/** Section A/B's ViewModel — the fields this view renders. */
interface FilmDetailVm {
  readonly title: string;
  readonly alternativeTitles: readonly AlternativeTitleVm[];
  readonly posterImage: string | null;
  /** Year, director, and runtime as one subtitle line, as `library.ts` does. */
  readonly subtitle: string;
  readonly genres: readonly string[];
  readonly tags: readonly string[];
  /**
   * The filled star layer's width as a percentage of the row (`average / 5 *
   * 100`), or `null` for unrated (FR-RAT-13) — `null` here suppresses the
   * whole star row rather than rendering a 0% fill (see the template).
   * Exact, unlike `ratingStars`' half-star rounding below: this is a display
   * of a computed mean, not a half-step input, so it shows the real value.
   */
  readonly averageFillPercent: number | null;
  readonly ratingLabel: string;
  /** The numeric average formatted to one decimal, or `null` for unrated (FR-RAT-13). */
  readonly averageRatingText: string | null;
  readonly createdAt: string;
  readonly updatedAt: string;
  /** Newest first — the backend already orders it that way; not re-sorted here. */
  readonly ratingHistory: readonly RatingHistoryVm[];
  /** Section A controls (phase 3, FR-LIB-06). */
  readonly isFavorite: boolean;
  readonly delayDays: number;
  /** User-entered Letterboxd link (REQ §4.1), `null` when never set. */
  readonly letterboxdUrl: string | null;
}

const timestampFormat = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' });
const dateFormat = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' });

/** The picker's five star positions — each renders one glyph plus two half-width hit targets (FR-RAT-02). */
const STAR_POSITIONS: readonly number[] = [1, 2, 3, 4, 5];

/**
 * Rounds to the nearest half star and maps each of the 5 positions to a
 * Material star icon. Duplicated from `library.ts`'s helper of the same name
 * (plan's deliberate cut #2) — extract to `shared/` only if a third caller
 * appears. Reused within this file for both the Add Rating picker and each
 * history entry (Section B); the Section A average uses an exact fill
 * instead (see `averageFillPercent`), since it displays a computed mean
 * rather than a half-step input.
 */
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

/** e.g. "19 Jun 2021 (1,904 days ago)" — calendar days, not elapsed hours, so "today"/"yesterday" read right regardless of time of day. */
function formatWatchDate(isoDate: string): string {
  const watchDate = new Date(isoDate);
  const today = new Date();
  const msPerDay = 86_400_000;
  const watchUtcDay = Date.UTC(watchDate.getFullYear(), watchDate.getMonth(), watchDate.getDate());
  const todayUtcDay = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate());
  const days = Math.round((todayUtcDay - watchUtcDay) / msPerDay);
  const suffix = days === 0 ? 'today' : days === 1 ? 'yesterday' : `${days.toLocaleString()} days ago`;
  return `${dateFormat.format(watchDate)} (${suffix})`;
}

function toRatingHistoryVm(entry: RatingHistoryEntry): RatingHistoryVm {
  return {
    id: entry.id,
    stars: ratingStars(entry.value),
    watchDate: formatWatchDate(entry.watchDate),
    createdAt: timestampFormat.format(new Date(entry.createdAt)),
  };
}

function toVm(film: FilmDetailModel): FilmDetailVm {
  return {
    title: film.primaryTitle,
    alternativeTitles: film.titles
      .filter((title) => !title.isPrimary)
      .map((title) => ({ value: title.value, isOriginal: title.isOriginal })),
    posterImage: film.posterImage,
    subtitle: [String(film.releaseYear), film.director, `${film.runtimeMinutes} min`].join(' • '),
    genres: film.genres,
    tags: film.tags,
    // `* 20`, not `/ 5 * 100` — equivalent, but the division route introduces
    // floating-point noise (3.3 → 65.999999999999996%) that this avoids.
    averageFillPercent: film.averageRating === null ? null : film.averageRating * 20,
    ratingLabel:
      film.averageRating === null ? 'Not rated' : `Average rating: ${film.averageRating.toFixed(1)} out of 5`,
    averageRatingText: film.averageRating === null ? null : film.averageRating.toFixed(1),
    createdAt: timestampFormat.format(new Date(film.createdAt)),
    updatedAt: timestampFormat.format(new Date(film.updatedAt)),
    ratingHistory: film.ratingHistory.map(toRatingHistoryVm),
    isFavorite: film.isFavorite,
    delayDays: film.delayDays,
    letterboxdUrl: film.letterboxdUrl,
  };
}

/** Formats a `Date` as `yyyy-MM-dd` in local time — `toISOString` would shift the day across time zones. */
function toIsoDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/** Surfaces the `core/errors.py` envelope's `message` (e.g. `FUTURE_WATCH_DATE`), falling back for network/unknown failures. */
function extractErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof HttpErrorResponse) {
    const body = error.error as { error?: { message?: string } } | null;
    if (body?.error?.message) return body.error.message;
  }
  return fallback;
}

@Component({
  selector: 'app-film-detail',
  imports: [
    EditableChips,
    MatButtonModule,
    MatCardModule,
    MatDatepickerModule,
    MatDividerModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatListModule,
    RouterLink,
  ],
  // The Add Rating form's `watch_date` picker (phase 2, FR-RAT-03) needs a
  // date adapter; native `Date` is enough — no extra date library. Scoped
  // here (not app-wide) so it lands in this lazy chunk, not the initial bundle.
  providers: [provideNativeDateAdapter()],
  templateUrl: './film-detail.html',
  styleUrl: './film-detail.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FilmDetail {
  private readonly films = inject(FilmFacade);
  private readonly ratings = inject(RatingFacade);
  private readonly tags = inject(TagFacade);
  private readonly genres = inject(GenreFacade);
  private readonly dialog = inject(MatDialog);
  private readonly router = inject(Router);
  private readonly navigationHistory = inject(NavigationHistoryService);

  /** Where the view's own back control (§6.5) returns to — see `NavigationHistoryService`. */
  protected readonly backTarget = this.navigationHistory.backTarget;
  protected readonly backLabel = this.navigationHistory.backLabel;

  /** Bound from the `film/:id` route param via `withComponentInputBinding()`. */
  readonly id = input.required<string>();

  constructor() {
    // Re-selects on every navigation between two `film/:id` routes — the
    // router reuses this component instance rather than recreating it.
    effect(() => this.films.select(this.id()));

    // Debounces the rewatch delay input (below): a number input's spinner
    // arrows fire a native `change` event per click, so five clicks would
    // otherwise mean five PATCHes.
    this.delayChange$.pipe(debounceTime(500), takeUntilDestroyed()).subscribe((value) => {
      // Re-checks against the current value at delivery time, not at the
      // time the user typed it — the debounce window may have collapsed a
      // "raise, then lower back to the original" sequence into a no-op.
      if (value === this.films.detail()?.delayDays) return;
      this.patch({ delayDays: value }, this.delayError, 'The rewatch delay could not be updated.');
    });

    // Read/edit toggle for the Letterboxd field: focuses the input on entering
    // edit mode, and returns focus to the edit button on leaving it (commit,
    // cancel, or Escape) — `library.ts`'s `searchInput` focus effect, adapted
    // for a two-way toggle via the `wasLetterboxdEditing` guard so the effect
    // does nothing on initial render, only on an actual open/close.
    effect(() => {
      const editing = this.letterboxdEditing();
      if (editing) {
        this.letterboxdInput()?.nativeElement.focus();
      } else if (this.wasLetterboxdEditing) {
        this.letterboxdEditButton()?.nativeElement.focus();
      }
      this.wasLetterboxdEditing = editing;
    });
  }

  protected readonly isLoading = this.films.detailIsLoading;
  protected readonly error = this.films.detailError;
  protected readonly notFound = this.films.detailNotFound;
  protected readonly vm = computed<FilmDetailVm | null>(() => {
    const film = this.films.detail();
    return film ? toVm(film) : null;
  });

  /** Retries whichever of the list request or the fallback fetch is unsettled. */
  protected reload(): void {
    this.films.reload();
  }

  // --- Add Rating (Section B, FR-RAT-01..04/12) ---------------------------

  protected readonly starPositions = STAR_POSITIONS;
  /**
   * `null` = nothing chosen yet, `'unrated'` = explicitly "Don't rate this",
   * a number = that star value. No default choice (FR-RAT-12) — the wire
   * payload's `value` is always sent explicitly regardless of which of the
   * latter two is picked (see `submitRating`).
   */
  protected readonly selectedValue = signal<number | 'unrated' | null>(null);
  /**
   * The half-star value under the pointer/focus, or `null` off the row —
   * previews a click's outcome without touching `selectedValue`. Left half
   * of star *n* previews `n - 0.5`, right half previews `n` (repo owner's
   * spec for FR-RAT-02's picker).
   */
  protected readonly hoverValue = signal<number | null>(null);
  /**
   * What the row currently renders: the hover preview if any, else the
   * selection — 0 when nothing numeric is selected, which makes `ratingStars`
   * below render five empty stars rather than the FR-RAT-13 "unrated" `null`.
   */
  private readonly pickerValue = computed<number>(() => {
    const selected = this.selectedValue();
    return this.hoverValue() ?? (typeof selected === 'number' ? selected : 0);
  });
  /** Reuses `ratingStars` (below) for the picker's fill logic — same half-star mapping as the average and history displays. */
  protected readonly pickerStars = computed<readonly string[]>(() => ratingStars(this.pickerValue()) ?? []);
  /** Today's date, also the datepicker's `[max]` (FR-RAT-03). */
  protected readonly today = new Date();
  protected readonly watchDate = signal<Date | null>(this.today);
  protected readonly isSubmittingRating = signal(false);
  protected readonly addRatingError = signal<string | null>(null);
  protected readonly deleteRatingError = signal<string | null>(null);

  /** e.g. "Rate 0.5 stars", "Rate 1 star", "Rate 4.5 stars" — singular only at exactly 1. */
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

  protected onSubmitRating(event: SubmitEvent): void {
    event.preventDefault();
    this.submitRating();
  }

  private submitRating(): void {
    const watchDate = this.watchDate();
    const selected = this.selectedValue();
    if (watchDate === null || selected === null || this.isSubmittingRating()) return;

    // FR-RAT-12: the API's `value` key is required even for "Don't rate this".
    const draft: RatingDraft = { value: selected === 'unrated' ? null : selected, watchDate: toIsoDate(watchDate) };
    this.isSubmittingRating.set(true);
    this.ratings.add(this.id(), draft).subscribe({
      next: () => {
        this.isSubmittingRating.set(false);
        this.addRatingError.set(null);
        this.selectedValue.set(null);
        this.watchDate.set(this.today);
      },
      error: (error: unknown) => {
        this.isSubmittingRating.set(false);
        this.addRatingError.set(extractErrorMessage(error, 'The rating could not be saved.'));
      },
    });
  }

  // --- Delete entry (Section B, FR-RAT-07) ---------------------------------

  protected deleteRating(ratingId: string): void {
    const film = this.vm();
    if (film === null) return;

    // FR-RAT-07: deleting the only rating deletes the whole film — state that
    // outcome plainly rather than hedge with "if it's the last rating".
    const isOnlyRating = film.ratingHistory.length === 1;
    const data: ConfirmDialogData = isOnlyRating
      ? {
          title: 'Delete the film?',
          message: `This is ${film.title}'s only rating. Deleting it deletes the whole film — this cannot be undone.`,
          confirmLabel: 'Delete film',
        }
      : {
          title: 'Delete this rating?',
          message: 'This cannot be undone.',
          confirmLabel: 'Delete',
        };
    this.dialog
      .open(ConfirmDialog, { data })
      .afterClosed()
      .subscribe((confirmed: boolean | undefined) => {
        if (!confirmed) return;
        this.ratings.remove(ratingId).subscribe({
          next: (result) => {
            this.deleteRatingError.set(null);
            if (result.filmDeleted) void this.router.navigateByUrl('/library');
          },
          error: (error: unknown) => {
            this.deleteRatingError.set(extractErrorMessage(error, 'The rating could not be deleted.'));
          },
        });
      });
  }

  // --- Section A controls (phase 3, FR-LIB-06/10..12) ----------------------

  protected readonly favoriteError = signal<string | null>(null);
  protected readonly delayError = signal<string | null>(null);
  protected readonly deleteFilmError = signal<string | null>(null);
  protected readonly letterboxdUrlError = signal<string | null>(null);

  private patch(patch: FilmPatch, errorSignal: WritableSignal<string | null>, fallback: string): void {
    this.films.update(this.id(), patch).subscribe({
      next: () => errorSignal.set(null),
      error: (error: unknown) => errorSignal.set(extractErrorMessage(error, fallback)),
    });
  }

  /** `PATCH /films/{id}` with only `is_favorite` — a heart, not a star (plan's UI-components section). */
  protected toggleFavorite(): void {
    const film = this.films.detail();
    if (film === null) return;
    this.patch({ isFavorite: !film.isFavorite }, this.favoriteError, 'The favourite flag could not be updated.');
  }

  /** Debounce subject for the rewatch delay input — see the constructor's subscription. */
  private readonly delayChange$ = new Subject<number>();

  /**
   * Native `change` event — fires once on blur/Enter for typed input, but
   * also once per click of a number input's spinner arrows, hence the
   * debounce (constructor) rather than patching straight away.
   */
  protected onDelayChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    const value = Number(input.value);
    const current = this.films.detail()?.delayDays ?? 0;
    if (!Number.isInteger(value) || value < 0) {
      input.value = String(current); // backend constraint is `ge=0` — reject client-side too
      return;
    }
    this.delayChange$.next(value);
  }

  /** Read/edit toggle state for the Letterboxd row — see the constructor's focus effect. */
  protected readonly letterboxdEditing = signal(false);
  private readonly letterboxdInput = viewChild<ElementRef<HTMLInputElement>>('letterboxdInput');
  private readonly letterboxdEditButton = viewChild<ElementRef<HTMLButtonElement>>('letterboxdEditButton');
  /** Guards the focus effect against firing on initial render — only a genuine toggle should move focus. */
  private wasLetterboxdEditing = false;

  protected startEditingLetterboxd(): void {
    this.letterboxdEditing.set(true);
  }

  /** Escape cancels without saving — the input is uncontrolled, so it simply unmounts with whatever was typed discarded. */
  protected cancelLetterboxdEdit(): void {
    this.letterboxdEditing.set(false);
  }

  /** Enter, or the confirm button, commits. Blank commits as `null` (clears the link, REQ §4.1); an unchanged value skips the PATCH. */
  protected commitLetterboxdEdit(rawValue: string): void {
    const trimmed = rawValue.trim();
    const value = trimmed === '' ? null : trimmed;
    this.letterboxdEditing.set(false);
    if (value === (this.films.detail()?.letterboxdUrl ?? null)) return;
    this.patch({ letterboxdUrl: value }, this.letterboxdUrlError, 'The Letterboxd link could not be updated.');
  }

  /** Confirm dialog (FR-LIB-11), then `DELETE /films/{id}`, then back to the Library. */
  protected confirmDeleteFilm(): void {
    const film = this.vm();
    if (film === null) return;
    const data: ConfirmDialogData = {
      title: 'Delete this film?',
      message: `Deleting ${film.title} removes it and its whole rating history. This cannot be undone.`,
      confirmLabel: 'Delete film',
    };
    this.dialog
      .open(ConfirmDialog, { data })
      .afterClosed()
      .subscribe((confirmed: boolean | undefined) => {
        if (!confirmed) return;
        this.films.remove(this.id()).subscribe({
          next: () => void this.router.navigateByUrl('/library'),
          error: (error: unknown) => {
            this.deleteFilmError.set(extractErrorMessage(error, 'The film could not be deleted.'));
          },
        });
      });
  }

  // --- Tags and genres (FR-TAG-03/06, REQ §4.4) ----------------------------

  protected readonly tagNames = this.tags.names;
  protected readonly genreNames = this.genres.names;
  protected readonly tagsError = signal<string | null>(null);
  protected readonly genresError = signal<string | null>(null);

  protected saveTags(tags: readonly string[]): void {
    this.saveLabels({ tags }, this.tagsError, 'The tags could not be updated.', this.tags);
  }

  protected saveGenres(genres: readonly string[]): void {
    this.saveLabels({ genres }, this.genresError, 'The genres could not be updated.', this.genres);
  }

  /**
   * `PATCH /films/{id}` with a complete label list (FR-TAG-03), then a
   * refresh of that vocabulary: the edit may have created a label
   * (FR-TAG-01) or left one on no film at all (FR-TAG-04), either of which
   * makes the autocomplete's copy stale. The facade applies the change
   * locally first and rolls it back on failure, like the other Section A
   * writes.
   */
  private saveLabels(
    patch: FilmPatch,
    errorSignal: WritableSignal<string | null>,
    fallback: string,
    vocabulary: { reload(): void },
  ): void {
    this.films.update(this.id(), patch).subscribe({
      next: () => {
        errorSignal.set(null);
        vocabulary.reload();
      },
      error: (error: unknown) => errorSignal.set(extractErrorMessage(error, fallback)),
    });
  }
}
