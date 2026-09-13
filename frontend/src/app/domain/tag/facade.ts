/**
 * Tag business logic (DESIGN §6.1) — the single API views call for the
 * FR-TAG-06 autocomplete vocabulary.
 *
 * There is no tag *write* API: assigning and removing tags is a film-level
 * edit (`FilmFacade.update` with `tags`), which is why this facade only
 * reads.
 */
import { Injectable, computed, inject } from '@angular/core';

import { TagApi } from './api';

@Injectable({ providedIn: 'root' })
export class TagFacade {
  private readonly api = inject(TagApi);

  /**
   * Every known tag name. The wire row's `id`/`created_at` stay in the data
   * layer — a tag is identified by its name everywhere above it (the film
   * payloads speak in names, and the backend dedupes them case-insensitively,
   * FR-TAG-02).
   */
  readonly names = computed<readonly string[]>(() => this.api.list.value().map((tag) => tag.name));

  /** Refetches after a film edit created a tag (FR-TAG-01) or orphaned one (FR-TAG-04). */
  reload(): void {
    this.api.list.reload();
  }
}
