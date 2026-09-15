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
import { MAT_NATIVE_DATE_FORMATS, provideNativeDateAdapter, type MatDateFormats } from '@angular/material/core';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatTimepickerModule } from '@angular/material/timepicker';
import { RouterLink } from '@angular/router';

import { RewatchFacade } from '../../domain/rewatch/facade';

/**
 * `MAT_NATIVE_DATE_FORMATS`'s `timeInput`/`timeOptionLabel` omit `hour12`, so
 * the timepicker otherwise follows the browser locale — AM/PM under `en-US`.
 * This app has no other locale-sensitive formatting to keep consistent with,
 * so it's pinned to 24-hour directly rather than via a locale swap.
 */
const TWENTY_FOUR_HOUR_FORMATS: MatDateFormats = {
  ...MAT_NATIVE_DATE_FORMATS,
  display: {
    ...MAT_NATIVE_DATE_FORMATS.display,
    timeInput: { hour: 'numeric', minute: 'numeric', hour12: false },
    timeOptionLabel: { hour: 'numeric', minute: 'numeric', hour12: false },
  },
};

@Component({
  selector: 'app-rewatch',
  imports: [
    MatButtonModule,
    MatCardModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatProgressBarModule,
    MatTimepickerModule,
    RouterLink,
  ],
  templateUrl: './rewatch.html',
  styleUrl: './rewatch.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [provideNativeDateAdapter(TWENTY_FOUR_HOUR_FORMATS)],
})
export class Rewatch {
  private readonly rewatch = inject(RewatchFacade);

  protected readonly cards = this.rewatch.cards;
  protected readonly doneBefore = this.rewatch.doneBefore;
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

  protected onDoneBeforeChange(cutoff: Date | null): void {
    if (cutoff !== null) this.rewatch.setDoneBefore(cutoff);
  }
}
