/**
 * The rewatch business-logic facade (DESIGN §6.1, §6.3) — the single API the view calls.
 *
 * The due-list arrives as bare `film_id`s (§5.8); this is where each one is
 * joined to the cached film metadata to make a card. The view therefore holds
 * no lookup logic and no ordering logic of its own.
 */
import { Injectable, computed, inject } from '@angular/core';

import { FilmFacade } from '../film/facade';
import { RewatchApi } from './api';
import { toRewatchCardVm, toRewatchSuggestion } from './mapper';
import type { RewatchCardVm } from './model';

@Injectable({ providedIn: 'root' })
export class RewatchFacade {
  private readonly api = inject(RewatchApi);
  private readonly films = inject(FilmFacade);

  /**
   * The §7.1 grid, in the algorithm's order (FR-RW-04) — this never sorts.
   *
   * A suggestion whose film the library does not hold is dropped rather than
   * rendered as a blank card: the two lists are fetched separately, so a film
   * deleted since the last daily run can still appear in the due-list. It
   * disappears for good at the next run.
   */
  readonly cards = computed<readonly RewatchCardVm[]>(() => {
    const byId = new Map(this.films.films().map((film) => [film.id, film]));
    return this.api.list.value().flatMap((dto) => {
      const suggestion = toRewatchSuggestion(dto);
      const film = byId.get(suggestion.filmId);
      return film === undefined ? [] : [toRewatchCardVm(film, suggestion)];
    });
  });

  /** Either request being in flight counts — a card needs both to have landed. */
  readonly isLoading = computed(() => this.api.list.isLoading() || this.films.isLoading());
  readonly error = computed(() => this.api.list.error() ?? this.films.error());

  /**
   * Drop a film from the displayed due-list (§6.3 optimistic removal).
   *
   * Called when a watch is logged for it anywhere in the app: a film watched
   * today will not be due again for a while, and waiting for tomorrow's run to
   * say so would leave it sitting in the grid. Local only — the daily job
   * stays authoritative and restores the film at the next fetch if it really
   * is still due, which makes this self-correcting rather than a guess.
   */
  removeFilm(filmId: string): void {
    this.api.list.value.update((suggestions) => suggestions.filter((suggestion) => suggestion.film_id !== filmId));
  }

  /** Re-fetch the due-list (from an error state). */
  reload(): void {
    this.api.list.reload();
  }
}
