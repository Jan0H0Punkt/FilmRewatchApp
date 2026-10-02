/**
 * The Rewatch Suggestion view (REQ §7.1) — the films that are due for another
 * watch, most overdue first.
 *
 * Per §6.1 the view calls facades only and holds no rules of its own: the
 * join, the ordering and the card shaping all happen in `domain/rewatch/`.
 * The one exception is the FR-RW-08 cap — its pure formula (`rewatchCap`)
 * lives in the rewatch domain too, but the design has the view itself read
 * `StatsFacade`/`SettingsFacade` and call it, since the cap only exists at
 * this view and needs data neither `RewatchFacade` nor the formula otherwise
 * has a reason to hold.
 *
 * There is deliberately no refresh control (§7.1) — the list re-reads when the
 * view opens, and the backend recomputes once a day (§5.8).
 */
import { ChangeDetectionStrategy, Component, computed, DestroyRef, effect, inject } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MAT_NATIVE_DATE_FORMATS, provideNativeDateAdapter, type MatDateFormats } from '@angular/material/core';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatTimepickerModule } from '@angular/material/timepicker';
import { MatTooltipModule } from '@angular/material/tooltip';
import { RouterLink } from '@angular/router';

import { ScrollMemoryService } from '../../core/scroll-memory';
import { rewatchCap } from '../../domain/rewatch/cap';
import { RewatchFacade } from '../../domain/rewatch/facade';
import type { RewatchCardVm } from '../../domain/rewatch/model';
import { SettingsFacade } from '../../domain/settings/facade';
import { StatsFacade } from '../../domain/stats/facade';
import { ScrollToTopFab } from '../../shared/scroll-to-top-fab/scroll-to-top-fab';
import { TruncatedTooltipDirective } from '../../shared/truncated-tooltip';
import { LetterboxdDialog } from './letterboxd-dialog';

/** Key under which this view's scroll offset is remembered (`ScrollMemoryService`). */
const SCROLL_KEY = 'rewatch';

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
    MatTooltipModule,
    RouterLink,
    ScrollToTopFab,
    TruncatedTooltipDirective,
  ],
  templateUrl: './rewatch.html',
  styleUrl: './rewatch.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [provideNativeDateAdapter(TWENTY_FOUR_HOUR_FORMATS)],
})
export class Rewatch {
  private readonly rewatch = inject(RewatchFacade);
  private readonly stats = inject(StatsFacade);
  private readonly settings = inject(SettingsFacade);
  private readonly scrollMemory = inject(ScrollMemoryService);
  private readonly dialog = inject(MatDialog);
  private hasRestoredScroll = false;

  /** The algorithm's due-list, before the §Cap filter — `cards` below is what's actually shown. */
  private readonly allCards = this.rewatch.cards;

  /**
   * `W`/`R` for the current calendar year (§Cap), picked the way `stats.ts`
   * picks its own default scope. `null` while `/stats` hasn't loaded or has
   * errored — that's the "fails open" case below, not a missing year block
   * (a year absent from `stats.years` is `W = R = 0` instead).
   */
  private readonly cap = computed<number | null>(() => {
    const stats = this.stats.stats();
    if (stats === null) return null;
    const year = stats.years.find((y) => y.year === new Date().getFullYear());
    return rewatchCap(
      this.settings.rewatchShare(),
      year?.watches ?? 0,
      year?.rewatches ?? 0,
      this.settings.watchIntervalDays(),
    );
  });

  /** The §7.1 grid: the due-list's prefix (FR-RW-04 never re-sorts), capped per FR-RW-08. */
  protected readonly cards = computed<readonly RewatchCardVm[]>(() => {
    const cap = this.cap();
    const all = this.allCards();
    return cap === null ? all : all.slice(0, cap);
  });

  protected readonly doneBefore = this.rewatch.doneBefore;
  /** Mirrors the library's own count line; the template hides it at zero, where the empty state already says so. */
  protected readonly countLabel = computed<string>(() => {
    const due = this.cards().length;
    return `${due} film${due === 1 ? '' : 's'} due`;
  });
  /**
   * "Showing k of n due films · t% rewatch target[ · 1 film every N days]" (FR-RW-08/09) — `null` when
   * there is no cap or the cap hides nothing, which is also when
   * `capNote()`'s caller falls back to the plain count/empty-state text
   * instead. Replaces `countLabel` rather than sitting beside it: both say
   * "how many", and this says it with the target too.
   */
  protected readonly capNote = computed<string | null>(() => {
    const cap = this.cap();
    const total = this.allCards().length;
    if (cap === null || cap >= total) return null;
    const days = this.settings.watchIntervalDays();
    const pace = days === null ? '' : ` · 1 film every ${days === 1 ? 'day' : `${days} days`}`;
    return `Showing ${cap} of ${total} due film${total === 1 ? '' : 's'} · ${this.settings.rewatchShare()}% rewatch target${pace}`;
  });
  protected readonly isLoading = this.rewatch.isLoading;
  protected readonly error = this.rewatch.error;

  constructor() {
    // See `RewatchFacade.onViewOpened` — this is what makes the docstring
    // above true rather than aspirational. `stats`/`settings` need the same
    // treatment: both are `providedIn: 'root'` singletons that fetch once at
    // construction, so without this a tab left open would cap against a
    // stale share or a stale year's watch count.
    this.rewatch.onViewOpened();
    this.stats.onViewOpened();
    this.settings.onViewOpened();

    // Restores the scroll offset saved when this view was last left — waits
    // for loading to finish so it lands in the real list, not the loading state.
    effect(() => {
      if (this.isLoading() || this.hasRestoredScroll) return;
      this.hasRestoredScroll = true;
      window.scrollTo(0, this.scrollMemory.restore(SCROLL_KEY));
    });

    inject(DestroyRef).onDestroy(() => this.scrollMemory.save(SCROLL_KEY, window.scrollY));
  }

  protected reload(): void {
    this.rewatch.reload();
  }

  protected onDoneBeforeChange(cutoff: Date | null): void {
    if (cutoff !== null) this.rewatch.setDoneBefore(cutoff);
  }

  /** The title icon: an existing link opens Letterboxd, a missing one opens the add-link dialog (`LetterboxdDialog`). */
  protected onLetterboxdClick(card: RewatchCardVm): void {
    if (card.letterboxdUrl !== null) {
      window.open(card.letterboxdUrl, '_blank', 'noopener,noreferrer');
      return;
    }
    this.dialog.open(LetterboxdDialog, { data: { filmId: card.id } });
  }
}
