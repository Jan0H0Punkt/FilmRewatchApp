/**
 * The Film form — routed twice (`core/routes.registry.ts`), one component in
 * two modes told apart by the `id` route param:
 *
 * - `films/new`: creates a film together with its mandatory first rating in
 *   one `POST /films` (FR-LIB-01..03), reached through the Library's search
 *   (`?title=` prefill) or its Add Film button
 *   (`open work/library-view/add-film-via-search.md`, work item 2).
 * - `film/:id/edit`: edits every field of an existing film in one
 *   `PATCH /films/{id}` (FR-LIB-06/07), reached from the detail view's Edit
 *   action. The rating block is create-only — an existing film's ratings are
 *   the detail view's rating history, not a form field.
 *
 * Edit mode lives here rather than inline on the detail view so the REQ §4.1
 * title rules (any number of rows, mutually exclusive Primary/Original) have
 * one implementation. §6.1: the view calls facades only, holds no rules of
 * its own.
 */
import { HttpErrorResponse } from '@angular/common/http';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  linkedSignal,
  signal,
} from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { provideNativeDateAdapter } from '@angular/material/core';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { Router, RouterLink } from '@angular/router';
import type { Observable } from 'rxjs';

import { NavigationHistoryService } from '../../core/navigation-history';
import { FilmFacade } from '../../domain/film/facade';
import type { FilmCreateInput, FilmDetail, FilmTitleInput } from '../../domain/film/model';
import { GenreFacade } from '../../domain/genre/facade';
import { TagFacade } from '../../domain/tag/facade';
import { EditableChips } from '../../shared/editable-chips/editable-chips';
import { ratingStarsFor } from '../../shared/rating-stars';

const MIN_RELEASE_YEAR = 1888; // REQ §4.1 — the year of the first film ever made, mirrors the backend bound.
/** The picker's five star positions — reused from `film-detail.ts`'s Add Rating control. */
const STAR_POSITIONS: readonly number[] = [1, 2, 3, 4, 5];

/** One title row's editable state (REQ §4.1 Title object) — `id` is a client-only key, never sent on the wire. */
interface TitleRowState {
  readonly id: number;
  readonly value: string;
  readonly isPrimary: boolean;
  readonly isOriginal: boolean;
}

/** A title row plus its mutual-exclusion disabled state, derived from its siblings on every render. */
interface TitleRowVm extends TitleRowState {
  readonly primaryDisabled: boolean;
  readonly originalDisabled: boolean;
  readonly canRemove: boolean;
}

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
    MatCheckboxModule,
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
  private readonly navigationHistory = inject(NavigationHistoryService);

  /** Bound from the `?title=` query param (`withComponentInputBinding()`) — the Library search's prefill. */
  readonly title = input<string>('');
  /**
   * Bound from the `film/:id/edit` route param. Declared without a default —
   * `withComponentInputBinding()` leaves it `undefined` on `films/new`, which
   * carries no such param, and that absence *is* the mode switch.
   */
  readonly id = input<string>();

  /** The film being edited, or `null` in create mode. */
  protected readonly filmId = computed<string | null>(() => this.id() ?? null);
  protected readonly isEditing = computed(() => this.filmId() !== null);

  constructor() {
    // Same `select` call the detail view makes: `films.detail()` is a lookup
    // into the library list, with a fallback `GET /films/{id}` on a miss — so
    // an edit URL opened directly (no list loaded yet) still resolves.
    effect(() => {
      const id = this.filmId();
      if (id !== null) this.films.select(id);
    });
  }

  /**
   * The selected film, but only once it is the one this route asked for —
   * `films.detail()` still holds the previously selected film for a tick after
   * `select`, and prefilling from that would seed the form with another film's
   * data.
   */
  private readonly film = computed<FilmDetail | null>(() => {
    const id = this.filmId();
    if (id === null) return null;
    const film = this.films.detail();
    return film !== null && film.id === id ? film : null;
  });

  /**
   * Edit mode only: true while the film is still being fetched, so the
   * template holds the form back (see `titles`). Both failure states have to
   * be excluded, or a 404 or a dead backend leaves this spinning for good.
   */
  protected readonly isLoadingFilm = computed(
    () => this.isEditing() && this.film() === null && !this.notFound() && !this.loadError(),
  );
  protected readonly notFound = this.films.detailNotFound;
  /** Whatever stopped the film loading, other than it not existing — `undefined` in create mode, which fetches nothing. */
  protected readonly loadError = computed(() => (this.isEditing() ? this.films.detailError() : undefined));
  /** Where the not-found state's own link goes, as on the detail view (§6.5). */
  protected readonly backTarget = this.navigationHistory.backTarget;
  protected readonly backLabel = this.navigationHistory.backLabel;

  protected readonly currentYear = new Date().getFullYear();
  protected readonly minReleaseYear = MIN_RELEASE_YEAR;

  /**
   * In edit mode, one row per stored title; in create mode, one row seeded
   * from `title`, Primary already checked — a film always has exactly one
   * primary title (REQ §4.1), so defaulting to unchecked would just make the
   * user tick a box that's true for every film with only one title. `?? ''`:
   * `withComponentInputBinding()` leaves the input `undefined` (not the
   * declared default) when the route carries no `title` query param at all,
   * e.g. reached without a search first.
   *
   * A `linkedSignal` so a direct `?title=` navigation still prefills it, and
   * so edit mode can seed from a film that arrives after first render. The
   * template holds the whole form back until it has (`isLoadingFilm`), so
   * that late reseed can never discard something already typed.
   * `addTitleRow`/`removeTitleRow`/`setTitleValue`/`toggleTitlePrimary`/
   * `toggleTitleOriginal` below are the only other writers.
   */
  protected readonly titles = linkedSignal<readonly TitleRowState[]>(() => {
    const film = this.film();
    if (film === null) return [{ id: 0, value: this.title() ?? '', isPrimary: true, isOriginal: false }];
    return film.titles.map((title, index) => ({
      id: index,
      value: title.value,
      isPrimary: title.isPrimary,
      isOriginal: title.isOriginal,
    }));
  });

  /**
   * Each row plus its disabled state: once any row has a flag set, every
   * *other* row's matching checkbox disables — covers rows added afterward
   * too, since this recomputes off the live list on every change.
   */
  protected readonly titleRows = computed<readonly TitleRowVm[]>(() => {
    const rows = this.titles();
    // A lone title has no other row to defer primacy to, so its Primary
    // checkbox is locked checked rather than just defaulted — there is
    // nothing a user unchecking it could mean.
    const singleRow = rows.length === 1;
    const anyPrimary = rows.some((row) => row.isPrimary);
    const anyOriginal = rows.some((row) => row.isOriginal);
    return rows.map((row) => ({
      ...row,
      primaryDisabled: singleRow || (anyPrimary && !row.isPrimary),
      originalDisabled: anyOriginal && !row.isOriginal,
      canRemove: rows.length > 1,
    }));
  });

  /** `max + 1` rather than a running counter, so the ids stay unique whichever way `titles` was seeded. */
  protected addTitleRow(): void {
    this.titles.update((rows) => [
      ...rows,
      { id: Math.max(...rows.map((row) => row.id)) + 1, value: '', isPrimary: false, isOriginal: false },
    ]);
  }

  /** No-op on the last remaining row — the backend requires at least one title. */
  protected removeTitleRow(id: number): void {
    this.titles.update((rows) => (rows.length > 1 ? rows.filter((row) => row.id !== id) : rows));
  }

  protected setTitleValue(id: number, value: string): void {
    this.titles.update((rows) => rows.map((row) => (row.id === id ? { ...row, value } : row)));
  }

  /** Toggles this row's flag; every other row's is forced off — mutual exclusion (REQ §4.1: at most one primary). */
  protected toggleTitlePrimary(id: number): void {
    this.titles.update((rows) =>
      rows.map((row) => (row.id === id ? { ...row, isPrimary: !row.isPrimary } : { ...row, isPrimary: false })),
    );
  }

  /** Same mutual exclusion as `toggleTitlePrimary`, independently — at most one original (REQ §4.1). */
  protected toggleTitleOriginal(id: number): void {
    this.titles.update((rows) =>
      rows.map((row) => (row.id === id ? { ...row, isOriginal: !row.isOriginal } : { ...row, isOriginal: false })),
    );
  }

  /** Every row non-blank, and — once there's more than one — exactly one marked primary (mirrors the backend's own rule). */
  protected readonly titlesValid = computed(() => {
    const rows = this.titles();
    if (rows.some((row) => row.value.trim() === '')) return false;
    return rows.length === 1 || rows.filter((row) => row.isPrimary).length === 1;
  });

  // Each field prefills from the film in edit mode and starts empty in create
  // mode — `linkedSignal` for the same reason `titles` above is one.
  protected readonly releaseYear = linkedSignal<number | null>(() => this.film()?.releaseYear ?? null);
  protected readonly director = linkedSignal(() => this.film()?.director ?? '');
  protected readonly runtimeMinutes = linkedSignal<number | null>(() => this.film()?.runtimeMinutes ?? null);
  protected readonly selectedGenres = linkedSignal<readonly string[]>(() => this.film()?.genres ?? []);
  protected readonly selectedTags = linkedSignal<readonly string[]>(() => this.film()?.tags ?? []);
  protected readonly posterImage = linkedSignal(() => this.film()?.posterImage ?? '');
  protected readonly letterboxdUrl = linkedSignal(() => this.film()?.letterboxdUrl ?? '');
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

  protected readonly letterboxdUrlValid = computed(() => {
    const value = this.letterboxdUrl().trim();
    return value === '' || isWellFormedHttpUrl(value);
  });

  protected readonly isValid = computed(() => {
    const year = this.releaseYear();
    const runtime = this.runtimeMinutes();
    return (
      this.titlesValid() &&
      year !== null &&
      year >= MIN_RELEASE_YEAR &&
      year <= this.currentYear &&
      this.director().trim() !== '' &&
      runtime !== null &&
      runtime >= 1 &&
      this.selectedGenres().length > 0 &&
      this.selectedTags().length > 0 &&
      this.posterImageValid() &&
      this.letterboxdUrlValid() &&
      // Create only: the first watch is part of `POST /films` (FR-LIB-03).
      // An edit touches no rating, so nothing here to require.
      (this.isEditing() || this.watchDate() !== null)
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
    if (!this.isValid() || year === null || runtime === null || this.isSubmitting()) return;

    const posterImage = this.posterImage().trim();
    const letterboxdUrl = this.letterboxdUrl().trim();
    // The fields both modes send. An edit patches all of them at once, which
    // `FilmUpdate` accepts as a full replacement (FR-LIB-06/07) — the user
    // edited a whole form, so "what changed" is not worth diffing for.
    const fields = {
      titles: this.titles().map<FilmTitleInput>((row) => ({
        value: row.value.trim(),
        isPrimary: row.isPrimary,
        isOriginal: row.isOriginal,
      })),
      releaseYear: year,
      director: this.director().trim(),
      runtimeMinutes: runtime,
      genres: this.selectedGenres(),
      tags: this.selectedTags(),
      posterImage: posterImage === '' ? null : posterImage,
      letterboxdUrl: letterboxdUrl === '' ? null : letterboxdUrl,
    };

    const id = this.filmId();
    if (id !== null) {
      // Back to the film that was being edited, not the Library — the user
      // came from there and wants to see the result.
      this.send(this.films.update(id, fields), `/film/${id}`, 'The changes could not be saved.');
      return;
    }

    const watchDate = this.watchDate();
    if (watchDate === null) return;
    const selectedValue = this.selectedValue();
    const payload: FilmCreateInput = {
      ...fields,
      watchDate: toIsoDate(watchDate),
      rating: selectedValue === 'unrated' ? null : selectedValue,
    };
    this.send(this.films.create(payload), '/library', 'The film could not be created.');
  }

  /** The shared tail of both submits: hold the button, then navigate on success or surface the failure. */
  private send(request: Observable<unknown>, target: string, fallback: string): void {
    this.isSubmitting.set(true);
    request.subscribe({
      next: () => {
        this.isSubmitting.set(false);
        void this.router.navigateByUrl(target);
      },
      error: (error: unknown) => {
        this.isSubmitting.set(false);
        this.submitError.set(extractErrorMessage(error, fallback));
      },
    });
  }
}
