/**
 * The settings facade (DESIGN §6.1) — the single API `views/settings/` and
 * `views/rewatch/` call for the FR-RW-08 rewatch-share (FR-RW-08) and
 * watch-pace (FR-RW-09) settings.
 */
import { Injectable, computed, inject, signal } from '@angular/core';

import { SettingsApi } from './api';
import { toSettings, toSettingsDto } from './mapper';
import type { Settings } from './model';

@Injectable({ providedIn: 'root' })
export class SettingsFacade {
  private readonly api = inject(SettingsApi);

  /**
   * `null` while `/settings` is loading, on a load error, or when the setting
   * is genuinely Off — all three read the same to every caller: the Rewatch
   * view's cap fails open on a `null` exactly the way it already does for a
   * failed `/stats` load (§Cap).
   */
  private readonly current = computed<Settings>(() =>
    this.api.settings.hasValue()
      ? toSettings(this.api.settings.value())
      : { rewatchShare: null, watchIntervalDays: null },
  );

  readonly rewatchShare = computed<number | null>(() => this.current().rewatchShare);

  /** FR-RW-09 — same `null` semantics as `rewatchShare`: not loaded, load error and Off all read `null`. */
  readonly watchIntervalDays = computed<number | null>(() => this.current().watchIntervalDays);

  /** Set only by a failed save — a failed *load* leaves the settings at `null`, same as Off, with nothing to alert on. */
  readonly error = signal<string | null>(null);

  setRewatchShare(value: number | null): void {
    this.save({ ...this.current(), rewatchShare: value }, 'The rewatch share could not be saved.');
  }

  setWatchIntervalDays(value: number | null): void {
    this.save({ ...this.current(), watchIntervalDays: value }, 'The watch pace could not be saved.');
  }

  /**
   * `PUT /settings` (one row, so both settings travel together). Applies the
   * new row immediately, so the Settings view's controls reflect the change
   * with no round-trip delay, and rolls it back on failure — the same
   * optimistic-write/rollback shape as `FilmFacade.update`. The rollback is
   * also what restores the controls: they read these signals, so setting the
   * previous row back re-selects it without the view doing anything itself.
   */
  private save(next: Settings, failure: string): void {
    const previous = this.current();
    this.error.set(null);
    this.api.settings.value.set(toSettingsDto(next));
    this.api.save(toSettingsDto(next)).subscribe({
      next: (dto) => this.api.settings.value.set(dto),
      error: () => {
        this.api.settings.value.set(toSettingsDto(previous));
        this.error.set(failure);
      },
    });
  }

  private hasOpened = false;

  /** Re-fetches on every open after the first — same rule as `StatsFacade.onViewOpened`. */
  onViewOpened(): void {
    if (this.hasOpened) this.api.settings.reload();
    this.hasOpened = true;
  }
}
