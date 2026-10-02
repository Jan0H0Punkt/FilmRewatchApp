/**
 * The Settings view (FR-RW-08/09) — the rewatch share and the watch pace; per
 * §6.1 the view calls `SettingsFacade` only and holds no rules.
 */
import { ChangeDetectionStrategy, Component, computed, inject, linkedSignal, signal } from '@angular/core';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSliderModule } from '@angular/material/slider';

import { SettingsFacade } from '../../domain/settings/facade';

@Component({
  selector: 'app-settings',
  imports: [MatCardModule, MatFormFieldModule, MatInputModule, MatSliderModule],
  templateUrl: './settings.html',
  styleUrl: './settings.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Settings {
  private readonly settings = inject(SettingsFacade);

  protected readonly error = this.settings.error;
  protected readonly percent = (value: number): string => `${value}%`;

  /**
   * The thumb's position — follows the drag before the save, and snaps back
   * with the facade on a rolled-back one. A stored Off (`null`) shows as 100%:
   * both mean no cap (`rewatchCap`), and Off is only replaced once the thumb moves.
   */
  protected readonly shown = linkedSignal(() => this.settings.rewatchShare() ?? 100);
  protected readonly valueLabel = computed(() => (this.shown() === 100 ? 'No limit' : `${this.shown()}% rewatches`));

  /** The pace field's text, following the facade (so a rolled-back save restores it). */
  protected readonly paceText = linkedSignal(() => String(this.settings.watchIntervalDays() ?? ''));
  /** Set when the field holds something that is not a whole number ≥ 1; nothing is saved then. */
  protected readonly paceInvalid = signal(false);
  /** FR-RW-09's "≈ X films per year" hint; `null` when the pace is Off. */
  protected readonly filmsPerYear = computed(() => {
    const days = this.settings.watchIntervalDays();
    return days === null ? null : Math.round(365 / days);
  });

  constructor() {
    this.settings.onViewOpened();
  }

  /** Fires on release, not per drag step, so one gesture is one save. */
  protected onRewatchShareChange(value: number): void {
    this.settings.setRewatchShare(value);
  }

  /** Fires on commit (blur/Enter), not per keystroke. Empty means Off. */
  protected onWatchPaceChange(raw: string): void {
    const days = raw.trim() === '' ? null : Number(raw);
    if (days !== null && (!Number.isInteger(days) || days < 1)) {
      this.paceInvalid.set(true);
      return;
    }
    this.paceInvalid.set(false);
    this.settings.setWatchIntervalDays(days);
  }
}
