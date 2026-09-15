/**
 * The Rewatch Suggestion view (REQ §7.1) — the films that are due for another
 * watch, most overdue first.
 *
 * Per §6.1 the view calls the facade only and holds no rules: the join, the
 * ordering and the card shaping all happen in `domain/rewatch/`, so this file
 * is the template's four states and nothing else.
 *
 * There is deliberately no refresh control (§7.1) — the list re-reads when the
 * view opens, and the backend recomputes once a day (§5.8).
 */
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { RouterLink } from '@angular/router';

import { RewatchFacade } from '../../domain/rewatch/facade';

@Component({
  selector: 'app-rewatch',
  imports: [MatButtonModule, MatCardModule, MatIconModule, MatProgressBarModule, RouterLink],
  templateUrl: './rewatch.html',
  styleUrl: './rewatch.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Rewatch {
  private readonly rewatch = inject(RewatchFacade);

  protected readonly cards = this.rewatch.cards;
  /** Mirrors the library's own count line; the template hides it at zero, where the empty state already says so. */
  protected readonly countLabel = computed<string>(() => {
    const due = this.cards().length;
    return `${due} film${due === 1 ? '' : 's'} due`;
  });
  protected readonly isLoading = this.rewatch.isLoading;
  protected readonly error = this.rewatch.error;

  constructor() {
    // See `RewatchFacade.onViewOpened` — this is what makes the docstring
    // above true rather than aspirational.
    this.rewatch.onViewOpened();
  }

  protected reload(): void {
    this.rewatch.reload();
  }
}
