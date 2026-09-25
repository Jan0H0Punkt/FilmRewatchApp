/**
 * The Statistics view — all-time and per-year viewing statistics
 * (docs/superpowers/specs/2026-09-25-statistics-design.md). Holds no rules:
 * every number comes from `StatsFacade`; the view only picks the block for
 * the selected scope and scales the bars.
 */
import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, linkedSignal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { RouterLink } from '@angular/router';

import { StatsFacade } from '../../domain/stats/facade';
import type { StatsBlock } from '../../domain/stats/model';

type Scope = number | 'all';

@Component({
  selector: 'app-stats',
  imports: [DecimalPipe, MatButtonModule, MatCardModule, MatChipsModule, MatProgressBarModule, RouterLink],
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

  /** Bar height in percent of the tallest bar in the same chart. */
  protected percent(count: number, all: readonly { readonly count: number }[]): number {
    return (count / Math.max(1, ...all.map((item) => item.count))) * 100;
  }
}
