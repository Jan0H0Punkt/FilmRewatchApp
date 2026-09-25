/**
 * The settings facade (DESIGN §6.1) — the single API `views/settings/` and
 * `views/rewatch/` call for the FR-RW-08 rewatch-share setting.
 */
import { Injectable, computed, inject, signal } from '@angular/core';

import { SettingsApi } from './api';
import { toSettings, toSettingsDto } from './mapper';

@Injectable({ providedIn: 'root' })
export class SettingsFacade {
  private readonly api = inject(SettingsApi);

  /**
   * `null` while `/settings` is loading, on a load error, or when the setting
   * is genuinely Off — all three read the same to every caller: the Rewatch
   * view's cap fails open on a `null` exactly the way it already does for a
   * failed `/stats` load (§Cap).
   */
  readonly rewatchShare = computed<number | null>(() =>
    this.api.settings.hasValue() ? toSettings(this.api.settings.value()).rewatchShare : null,
  );

  /** Set only by a failed `setRewatchShare` — a failed *load* leaves `rewatchShare` at `null`, same as Off, with nothing to alert on. */
  readonly error = signal<string | null>(null);

  /**
   * `PUT /settings`. Applies the new value immediately, so the Settings
   * view's `mat-select` reflects the pick with no round-trip delay, and rolls
   * it back on failure — the same optimistic-write/rollback shape as
   * `FilmFacade.update`. The rollback is also what restores the `mat-select`:
   * its `[value]` binding reads this signal, so setting it back to `previous`
   * re-selects that option without the view doing anything itself.
   */
  setRewatchShare(value: number | null): void {
    const previous = this.rewatchShare();
    this.error.set(null);
    this.api.settings.value.set(toSettingsDto(value));
    this.api.save(toSettingsDto(value)).subscribe({
      next: (dto) => this.api.settings.value.set(dto),
      error: () => {
        this.api.settings.value.set(toSettingsDto(previous));
        this.error.set('The rewatch share could not be saved.');
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
