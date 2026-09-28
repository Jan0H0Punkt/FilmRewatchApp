/**
 * The Letterboxd facade (DESIGN §6.1) — the single API `views/letterboxd/`
 * and the navigation badge call (REQ §5.7).
 */
import { Injectable, computed, inject, signal } from '@angular/core';
import type { Observable } from 'rxjs';

import { FilmFacade } from '../film/facade';
import { LetterboxdApi } from './api';
import { toLetterboxdEntry } from './mapper';
import type { LetterboxdEntry } from './model';

@Injectable({ providedIn: 'root' })
export class LetterboxdFacade {
  private readonly api = inject(LetterboxdApi);
  private readonly films = inject(FilmFacade);

  /** Empty while loading and on error — `hasValue()` guards `value()`, which throws once the resource has errored. */
  readonly entries = computed<readonly LetterboxdEntry[]>(() =>
    this.api.entries.hasValue() ? this.api.entries.value().map(toLetterboxdEntry) : [],
  );
  readonly openCount = computed(() => this.entries().length);
  readonly isLoading = computed(() => this.api.entries.isLoading());
  readonly loadFailed = computed(() => this.api.entries.error() !== undefined);
  /** True while an action runs — the view disables every action button meanwhile. */
  readonly isBusy = signal(false);
  readonly actionError = signal<string | null>(null);

  private hasOpened = false;

  /** Re-fetches on every open after the first — same rule as `StatsFacade.onViewOpened`. */
  onViewOpened(): void {
    if (this.hasOpened) this.api.entries.reload();
    this.hasOpened = true;
  }

  reload(): void {
    this.api.entries.reload();
  }

  /** Adds the watch to `filmId` (FR-LBX-06); the library reloads so the film's new watch shows everywhere. */
  assign(entryId: string, filmId: string): void {
    this.run(this.api.assign(entryId, filmId), 'The watch could not be added.', () => this.films.reload());
  }

  dismiss(entryId: string): void {
    this.run(this.api.dismiss(entryId), 'The entry could not be dismissed.');
  }

  sync(): void {
    this.run(this.api.sync(), 'Letterboxd could not be reached.');
  }

  private run(request: Observable<unknown>, failure: string, onSuccess: () => void = () => undefined): void {
    this.actionError.set(null);
    this.isBusy.set(true);
    request.subscribe({
      next: () => {
        this.isBusy.set(false);
        onSuccess();
        this.api.entries.reload();
      },
      error: () => {
        this.isBusy.set(false);
        this.actionError.set(failure);
      },
    });
  }
}
