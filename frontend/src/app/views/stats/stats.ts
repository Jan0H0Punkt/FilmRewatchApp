/**
 * The Statistics view — all-time and per-year viewing statistics
 * (docs/superpowers/specs/2026-09-25-statistics-design.md). Holds no rules:
 * every number comes from `StatsFacade`; the view only picks the block for
 * the selected scope and scales the bars.
 */
import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, linkedSignal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatCardModule } from '@angular/material/card';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatTooltipModule } from '@angular/material/tooltip';
import { RouterLink } from '@angular/router';

import { StatsFacade } from '../../domain/stats/facade';
import type { StatsBlock } from '../../domain/stats/model';
import { TruncatedTooltipDirective } from '../../shared/truncated-tooltip';

interface Counted {
  readonly count: number;
}

interface Scored {
  readonly score: number;
}

type Scope = number | 'all';

@Component({
  selector: 'app-stats',
  imports: [
    DecimalPipe,
    MatButtonModule,
    MatButtonToggleModule,
    MatCardModule,
    MatProgressBarModule,
    MatTooltipModule,
    RouterLink,
    TruncatedTooltipDirective,
  ],
  templateUrl: './stats.html',
  styleUrl: './stats.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Stats {
  private readonly facade = inject(StatsFacade);

  protected readonly stats = this.facade.stats;
  protected readonly isLoading = this.facade.isLoading;
  protected readonly error = this.facade.error;

  /** The current year once the data holds it, otherwise all time; the user's pick after that. */
  protected readonly scope = linkedSignal<Scope>(() => {
    const thisYear = new Date().getFullYear();
    return this.stats()?.years.some((y) => y.year === thisYear) ? thisYear : 'all';
  });

  protected readonly block = computed<StatsBlock | null>(() => {
    const stats = this.stats();
    const scope = this.scope();
    if (stats === null) return null;
    return scope === 'all' ? stats.total : (stats.years.find((y) => y.year === scope) ?? stats.total);
  });

  constructor() {
    this.facade.onViewOpened();
  }

  protected select(scope: Scope): void {
    this.scope.set(scope);
  }

  protected reload(): void {
    this.facade.reload();
  }

  /** Bar size in percent of the tallest value in the same chart. */
  protected percent(value: number, all: readonly number[]): number {
    return (value / Math.max(1, ...all)) * 100;
  }

  protected counts(items: readonly Counted[]): number[] {
    return items.map((item) => item.count);
  }

  protected scores(items: readonly Scored[]): number[] {
    return items.map((item) => item.score);
  }

  /**
   * The all-time chart's buckets are 4-digit years, which overlap at phone
   * width once ~12+ years are tracked; the year scope's month labels ("1"…
   * "12") are short enough already. `aria-label` on the bar still carries
   * the full label.
   */
  protected barLabel(label: string): string {
    return this.scope() === 'all' ? `'${label.slice(-2)}` : label;
  }
}
