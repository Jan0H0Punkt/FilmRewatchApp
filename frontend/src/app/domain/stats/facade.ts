/** The stats facade (DESIGN §6.1) — the single API `views/stats/` calls. */
import { Injectable, computed, inject } from '@angular/core';

import { StatsApi } from './api';
import { toStats } from './mapper';
import type { Stats } from './model';

@Injectable({ providedIn: 'root' })
export class StatsFacade {
  private readonly api = inject(StatsApi);

  /** `null` until loaded and on error — `hasValue()` guards `value()`, which throws once the resource has errored. */
  readonly stats = computed<Stats | null>(() => (this.api.stats.hasValue() ? toStats(this.api.stats.value()) : null));
  readonly isLoading = computed(() => this.api.stats.isLoading());
  readonly error = computed(() => this.api.stats.error());

  reload(): void {
    this.api.stats.reload();
  }

  private hasOpened = false;

  /**
   * Refetches on every open after the first, so a watch logged elsewhere shows
   * up — `httpResource` in a root service fetches once, at construction. The
   * first open is that construction-time fetch. Same rule as `RewatchFacade.onViewOpened`.
   */
  onViewOpened(): void {
    if (this.hasOpened) this.api.stats.reload();
    this.hasOpened = true;
  }
}
