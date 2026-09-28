/**
 * The Letterboxd review list (REQ §5.7, FR-LBX-06): every new Letterboxd diary
 * entry waits here for approval. Per §6.1 the view calls facades only.
 */
import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatDialog } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { RouterLink } from '@angular/router';

import { LetterboxdFacade } from '../../domain/letterboxd/facade';
import type { LetterboxdEntry } from '../../domain/letterboxd/model';
import { ConfirmDialog, type ConfirmDialogData } from '../../shared/confirm-dialog/confirm-dialog';
import { ratingLabelFor, ratingStarsFor } from '../../shared/rating-stars';
import { AssignDialog, type AssignDialogData } from './assign-dialog';

@Component({
  selector: 'app-letterboxd',
  imports: [DatePipe, MatButtonModule, MatCardModule, MatIconModule, MatProgressBarModule, RouterLink],
  templateUrl: './letterboxd.html',
  styleUrl: './letterboxd.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Letterboxd {
  private readonly letterboxd = inject(LetterboxdFacade);
  private readonly dialog = inject(MatDialog);

  protected readonly entries = this.letterboxd.entries;
  protected readonly isLoading = this.letterboxd.isLoading;
  protected readonly loadFailed = this.letterboxd.loadFailed;
  protected readonly isBusy = this.letterboxd.isBusy;
  protected readonly actionError = this.letterboxd.actionError;
  protected readonly stars = ratingStarsFor;
  protected readonly ratingLabel = ratingLabelFor;

  constructor() {
    this.letterboxd.onViewOpened();
  }

  /** The film form's Letterboxd prefill params (FR-LBX-06) — names match its inputs. */
  protected createParams(entry: LetterboxdEntry): Record<string, string> {
    return {
      title: entry.filmTitle,
      year: String(entry.filmYear),
      letterboxdLink: entry.filmUrl,
      watchedOn: entry.watchedDate,
      ...(entry.rating !== null ? { rating: String(entry.rating) } : {}),
      ...(entry.rewatch ? { rewatch: 'true' } : {}),
    };
  }

  /** Adds the entry's watch to the film the sync matched (FR-LBX-06). */
  protected approve(entry: LetterboxdEntry): void {
    if (entry.suggestedFilm !== null) this.letterboxd.assign(entry.id, entry.suggestedFilm.id);
  }

  /**
   * Approve for a film the user picks instead of the suggestion — for a wrong
   * or missing match of a film already in the library (FR-LBX-06).
   */
  protected assign(entry: LetterboxdEntry): void {
    this.dialog
      .open<AssignDialog, AssignDialogData, string>(AssignDialog, {
        data: { filmTitle: entry.filmTitle },
        width: '32rem',
      })
      .afterClosed()
      .subscribe((filmId) => {
        if (filmId) this.letterboxd.assign(entry.id, filmId);
      });
  }

  protected dismiss(entry: LetterboxdEntry): void {
    this.dialog
      .open<ConfirmDialog, ConfirmDialogData, boolean>(ConfirmDialog, {
        data: {
          title: 'Dismiss entry?',
          message: `“${entry.filmTitle}” will not be added. This cannot be undone.`,
          confirmLabel: 'Dismiss',
        },
      })
      .afterClosed()
      .subscribe((confirmed) => {
        if (confirmed) this.letterboxd.dismiss(entry.id);
      });
  }

  protected sync(): void {
    this.letterboxd.sync();
  }

  protected reload(): void {
    this.letterboxd.reload();
  }
}
