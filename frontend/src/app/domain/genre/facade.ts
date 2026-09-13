/**
 * Genre business logic (DESIGN §6.1) — the single API views call for the
 * genre autocomplete vocabulary.
 *
 * Read-only: assigning and removing genres is a film-level edit
 * (`FilmFacade.update` with `genres`).
 */
import { Injectable, computed, inject } from '@angular/core';

import { GenreApi } from './api';

@Injectable({ providedIn: 'root' })
export class GenreFacade {
  private readonly api = inject(GenreApi);

  /** Every known genre name — a genre is identified by its name above the data layer, as a tag is. */
  readonly names = computed<readonly string[]>(() => this.api.list.value().map((genre) => genre.name));

  /** Refetches after a film edit created a genre or orphaned one. */
  reload(): void {
    this.api.list.reload();
  }
}
