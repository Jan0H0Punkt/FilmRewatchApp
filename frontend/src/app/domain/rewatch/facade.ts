/**
 * The rewatch business-logic facade (DESIGN §6.1, §6.3) — the single API the view calls.
 *
 * The due-list arrives as bare `film_id`s (§5.8); this is where each one is
 * joined to the cached film metadata to make a card. The view therefore holds
 * no lookup logic and no ordering logic of its own.
 */
import { Injectable, computed, inject, linkedSignal, type ResourceStatus } from '@angular/core';

import { FilmFacade } from '../film/facade';
import type { RewatchSuggestionDto } from './api';
import { RewatchApi } from './api';
import { toRewatchCardVm, toRewatchSuggestion } from './mapper';
import type { RewatchCardVm } from './model';

@Injectable({ providedIn: 'root' })
export class RewatchFacade {
  private readonly api = inject(RewatchApi);
  private readonly films = inject(FilmFacade);

  /**
   * `api.list.value()`, guarded against the error state.
   *
   * In Angular 22, `httpResource.value()` does not fall back to
   * `defaultValue` once the resource has errored — it THROWS
   * `ResourceValueError`. `cards` below reads this instead of `api.list`
   * directly, so a failed `/rewatch-suggestions` fetch keeps showing the
   * last successfully fetched due-list rather than freezing the view.
   * `FilmFacade.films` carries the equivalent guard for `/films` — see its
   * `listSafe`; both are read below, so either failing alone still yields a
   * card list rather than a throw.
   */
  private readonly suggestions = linkedSignal<ResourceStatus, readonly RewatchSuggestionDto[]>({
    source: () => this.api.list.status(),
    computation: (status, previous) => (status === 'error' ? (previous?.value ?? []) : this.api.list.value()),
  });

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
    return this.suggestions().flatMap((dto) => {
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
    this.api.removeFilm(filmId);
  }

  /**
   * Re-fetch both requests `cards` depends on (from an error state).
   *
   * Reloading only `api.list` left "Try again" dead whenever `/films` was
   * the request that actually failed — the due-list reload would succeed
   * and `error` would still read `films.error()`. `FilmFacade.reload()`
   * retries `/films` (and its rare detail fallback).
   */
  reload(): void {
    this.api.list.reload();
    this.films.reload();
  }

  private hasOpened = false;

  /**
   * Re-reads the due-list each time the Rewatch view opens (design §4.3).
   *
   * `RewatchApi` is `providedIn: 'root'`, and `httpResource` fetches only
   * once, at construction — so without this, a tab left open across the
   * backend's daily recompute would show a stale list forever. Skips the
   * very first call: that first open is already covered by `api.list`'s
   * own construction-time fetch, so reloading again immediately would just
   * duplicate the request.
   */
  onViewOpened(): void {
    if (this.hasOpened) this.api.list.reload();
    this.hasOpened = true;
  }
}
