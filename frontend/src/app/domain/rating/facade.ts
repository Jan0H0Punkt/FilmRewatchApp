/**
 * The rating business-logic facade (DESIGN §6.1) — the single API the view calls.
 *
 * Injects `FilmFacade` and applies each write's result to its local state
 * itself, so the view makes one call, not two, and never refetches (see
 * `FilmFacade`'s class doc). This mirrors the backend, where
 * `app/ratings/router.py` deliberately depends on `FilmService` for the same
 * reason (the last-rating-deletes-the-film bookkeeping). A logged watch also
 * updates the rewatch due-list the same way (§6.3 optimistic removal).
 */
import { Injectable, inject } from '@angular/core';
import { type Observable, map, tap } from 'rxjs';

import { FilmFacade } from '../film/facade';
import { RewatchFacade } from '../rewatch/facade';
import { RatingApi } from './api';
import { toRatingCreateDto, toRatingDeletionResult } from './mapper';
import type { RatingDeletionResult, RatingDraft } from './model';

@Injectable({ providedIn: 'root' })
export class RatingFacade {
  private readonly api = inject(RatingApi);
  private readonly films = inject(FilmFacade);
  private readonly rewatch = inject(RewatchFacade);

  /** `POST /films/{id}/ratings`; on success, prepends the new entry and recomputes the average locally. */
  add(filmId: string, draft: RatingDraft): Observable<void> {
    return this.api.add(filmId, toRatingCreateDto(draft)).pipe(
      tap((entry) => {
        this.films.applyRatingAdded(filmId, entry);
        // §6.3 optimistic removal: a film watched today will not be due again
        // for a while, so it leaves the rewatch grid now rather than at the
        // next daily run. Self-correcting — tomorrow's fetch restores it if
        // the algorithm disagrees.
        this.rewatch.removeFilm(filmId);
      }),
      map(() => undefined),
    );
  }

  /**
   * `DELETE /ratings/{id}`. When the film survived, removes the entry and
   * recomputes its average locally; when `filmDeleted: true`, the backend
   * deleted the whole film along with its last rating — the view navigates
   * to the Library instead of showing a stale detail.
   */
  remove(ratingId: string): Observable<RatingDeletionResult> {
    return this.api.remove(ratingId).pipe(
      map(toRatingDeletionResult),
      tap((result) => this.films.applyRatingRemoved(result.filmId, result.ratingId, result.filmDeleted)),
    );
  }
}
