/**
 * The Settings view (FR-RW-08) — so far just the rewatch-share setting; per
 * §6.1 the view calls `SettingsFacade` only and holds no rules.
 */
import { ChangeDetectionStrategy, Component, computed, inject, linkedSignal } from '@angular/core';
import { MatCardModule } from '@angular/material/card';
import { MatSliderModule } from '@angular/material/slider';

import { SettingsFacade } from '../../domain/settings/facade';

@Component({
  selector: 'app-settings',
  imports: [MatCardModule, MatSliderModule],
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

  constructor() {
    this.settings.onViewOpened();
  }

  /** Fires on release, not per drag step, so one gesture is one save. */
  protected onRewatchShareChange(value: number): void {
    this.settings.setRewatchShare(value);
  }
}
