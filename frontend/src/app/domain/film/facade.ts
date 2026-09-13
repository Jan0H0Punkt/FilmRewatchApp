/**
 * The film business-logic facade (DESIGN §6.1) — the single API views call.
 *
 * Wraps the data layer's resource so views see domain models and plain state
 * signals, never DTOs or HTTP.
 *
 * `GET /films` returns the full §7.3 projection for every film, so the
 * detail view is just a `computed` lookup into `list` (see `detail` below).
 * `FilmApi.detail` is a rare fallback `GET /films/{id}` for a `selectedId`
 * `list` doesn't hold; it folds its result into `list` itself, so `list`
 * stays the single copy every local write touches.
 *
 * Writes update `list` locally instead of refetching (the repo owner's call,
 * reversing the plan's deliberate cut #3 — a write already returns
 * success/error over the wire, so a second round trip to learn what it just
 * told us is redundant). `httpResource.value` is a `WritableSignal`, so a
 * local write is `.set()`/`.update()`, no parallel state store needed.
 */
import { HttpErrorResponse } from '@angular/common/http';
import { Injectable, computed, inject } from '@angular/core';
import { type Observable, catchError, map, tap, throwError } from 'rxjs';

import type { FilmDto, RatingEntryDto } from './api';
import { FilmApi } from './api';
import { toFilm, toFilmDetail, toFilmUpdateDto } from './mapper';
import type { Film, FilmDetail, FilmPatch } from './model';

@Injectable({ providedIn: 'root' })
export class FilmFacade {
  private readonly api = inject(FilmApi);

  /** The whole library, primary-title ordered; empty while loading. */
  readonly films = computed<readonly Film[]>(() => this.api.list.value().map(toFilm));
  readonly isLoading = this.api.list.isLoading;
  readonly error = this.api.list.error;

  /** Re-fetch the library (after a create, or from an error state) — and retry a stuck fallback fetch, if any. */
  reload(): void {
    this.api.list.reload();
    this.api.detail.reload();
  }

  /** Selects the film the detail view shows — a lookup into `list`; triggers `api.detail`'s fallback fetch only on a miss. */
  select(id: string): void {
    this.api.selectedId.set(id);
  }

  /**
   * `null` when nothing is selected, or when `selectedId` isn't (yet) in
   * `list`. The latter is transient while `api.detail`'s fallback fetch is
   * in flight — `detailIsLoading`/`detailNotFound` below tell the view
   * which is which.
   */
  readonly detail = computed<FilmDetail | null>(() => {
    const id = this.api.selectedId();
    if (id === null) return null;
    const dto = this.api.list.value().find((film) => film.id === id);
    return dto ? toFilmDetail(dto) : null;
  });
  /** Either request being in flight counts — the fallback fetch is invisible until it resolves. */
  readonly detailIsLoading = computed(() => this.api.list.isLoading() || this.api.detail.isLoading());
  /**
   * True once the fallback fetch has settled with a 404 — `selectedId`
   * genuinely isn't a film (stale bookmark, hand-typed id, deleted film).
   * The view renders this as its terminal not-found state, distinct from
   * `detailError` below.
   */
  readonly detailNotFound = computed(() => {
    const error = this.api.detail.error();
    return error instanceof HttpErrorResponse && error.status === 404;
  });
  /** Any other failure of either request — a 404 fallback is `detailNotFound`, not this. */
  readonly detailError = computed(() =>
    this.detailNotFound() ? undefined : (this.api.list.error() ?? this.api.detail.error()),
  );

  /** Finds `id`'s current DTO in `list`. */
  private findFilm(id: string): FilmDto | undefined {
    return this.api.list.value().find((film) => film.id === id);
  }

  /** Applies `updater` to `id`'s DTO in `list`, wherever it's present. */
  private updateFilm(id: string, updater: (film: FilmDto) => FilmDto): void {
    this.api.list.value.update((films) => films.map((film) => (film.id === id ? updater(film) : film)));
  }

  /** Drops `id` from `list` and clears `selectedId` — the film stopped existing. */
  private removeFilmLocally(id: string): void {
    this.api.list.value.update((films) => films.filter((film) => film.id !== id));
    this.api.selectedId.set(null);
  }

  /**
   * `PATCH /films/{id}` with a single changed field (FR-LIB-06). Applies the
   * change to `list` immediately for instant feedback (`detail` sees it too
   * — it's a lookup into `list`); on success merges the response body in
   * (it carries the authoritative `updated_at` etc.); on error rolls the
   * touched fields back to their pre-write values and re-throws so the
   * view's error signal still gets set.
   */
  update(id: string, patch: FilmPatch): Observable<void> {
    const film = this.findFilm(id);
    const previous: Pick<FilmDto, 'is_favorite' | 'delay_days'> | undefined = film
      ? { is_favorite: film.is_favorite, delay_days: film.delay_days }
      : undefined;

    this.updateFilm(id, (current) => ({
      ...current,
      ...(patch.isFavorite !== undefined ? { is_favorite: patch.isFavorite } : {}),
      ...(patch.delayDays !== undefined ? { delay_days: patch.delayDays } : {}),
    }));

    return this.api.update(id, toFilmUpdateDto(patch)).pipe(
      tap((updated) => this.updateFilm(id, () => updated)),
      catchError((error: unknown) => {
        if (previous) this.updateFilm(id, (current) => ({ ...current, ...previous }));
        return throwError(() => error);
      }),
      map(() => undefined),
    );
  }

  /**
   * `POST /films/{id}/ratings` success handler (FR-RAT-01..04): prepends the
   * returned entry to `rating_history` — no refetch. `averageRating` is
   * derived from that history by the mapper on the next read, so it updates
   * with no further work here.
   */
  applyRatingAdded(filmId: string, entry: RatingEntryDto): void {
    this.updateFilm(filmId, (film) => {
      const ratingHistory = [entry, ...film.rating_history];
      return { ...film, rating_history: ratingHistory };
    });
  }

  /**
   * `DELETE /ratings/{id}` success handler (FR-RAT-07). When the film
   * survived, removes the entry — the mapper derives the updated average
   * from what's left; when its last rating took the film with it, drops the
   * film from `list` instead — the view still navigates to the Library
   * either way.
   */
  applyRatingRemoved(filmId: string, ratingId: string, filmDeleted: boolean): void {
    if (filmDeleted) {
      this.removeFilmLocally(filmId);
      return;
    }
    this.updateFilm(filmId, (film) => {
      const ratingHistory = film.rating_history.filter((entry) => entry.id !== ratingId);
      return { ...film, rating_history: ratingHistory };
    });
  }

  /** `DELETE /films/{id}` (FR-LIB-10..12). The view navigates to the Library on success. */
  remove(id: string): Observable<void> {
    return this.api.remove(id).pipe(
      tap(() => this.removeFilmLocally(id)),
      map(() => undefined),
    );
  }
}
