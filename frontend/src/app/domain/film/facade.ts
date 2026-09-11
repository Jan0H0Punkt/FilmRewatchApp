/**
 * The film business-logic facade (DESIGN §6.1) — the single API views call.
 *
 * Wraps the data layer's resource so views see domain models and plain state
 * signals, never DTOs or HTTP.
 */
import { Injectable, computed, inject } from '@angular/core';

import { FilmApi } from './api';
import { toFilm } from './mapper';
import type { Film } from './model';

@Injectable({ providedIn: 'root' })
export class FilmFacade {
  private readonly api = inject(FilmApi);

  /** The whole library, primary-title ordered; empty while loading. */
  readonly films = computed<readonly Film[]>(() => this.api.list.value().map(toFilm));
  readonly isLoading = this.api.list.isLoading;
  readonly error = this.api.list.error;

  /** Re-fetch the library (after a create, or from an error state). */
  reload(): void {
    this.api.list.reload();
  }
}
