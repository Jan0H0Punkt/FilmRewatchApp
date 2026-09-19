/**
 * Prompts for a Letterboxd URL and saves it directly — opened by the Rewatch
 * card's title icon (§7.1) when a film has none yet. Self-contained (does its
 * own `PATCH` via `FilmFacade`) rather than handing the value back to the
 * view: the view has one card per film, not a per-card error signal to wire.
 */
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';

import { FilmFacade } from '../../domain/film/facade';

export interface LetterboxdDialogData {
  readonly filmId: string;
}

@Component({
  selector: 'app-letterboxd-dialog',
  imports: [MatButtonModule, MatDialogModule, MatFormFieldModule, MatInputModule],
  template: `
    <h2 matDialogTitle>Add a Letterboxd link</h2>
    <mat-dialog-content>
      <!-- The top margin isn't decorative: flush against mat-dialog-content's top edge, the
           outline's floating label gets clipped by the content panel's own overflow. -->
      <mat-form-field subscriptSizing="dynamic" style="margin-top: 0.5rem; width: 100%">
        <mat-label>Letterboxd URL</mat-label>
        <input
          #urlInput
          matInput
          type="url"
          [value]="url()"
          (input)="url.set(urlInput.value)"
          (keydown.enter)="save()"
        />
      </mat-form-field>
      @if (error()) {
        <p style="color: var(--mat-sys-error); margin: 0.5rem 0 0;" role="alert">{{ error() }}</p>
      }
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button matButton type="button" [mat-dialog-close]="undefined">Cancel</button>
      <button matButton="filled" type="button" [disabled]="url().trim() === '' || isSaving()" (click)="save()">
        Save
      </button>
    </mat-dialog-actions>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LetterboxdDialog {
  private readonly data = inject<LetterboxdDialogData>(MAT_DIALOG_DATA);
  private readonly dialogRef = inject(MatDialogRef<LetterboxdDialog>);
  private readonly films = inject(FilmFacade);

  protected readonly url = signal('');
  protected readonly isSaving = signal(false);
  protected readonly error = signal<string | null>(null);

  protected save(): void {
    const value = this.url().trim();
    if (value === '' || this.isSaving()) return;
    this.isSaving.set(true);
    this.films.update(this.data.filmId, { letterboxdUrl: value }).subscribe({
      next: () => this.dialogRef.close(),
      error: () => {
        this.isSaving.set(false);
        this.error.set('The link could not be saved.');
      },
    });
  }
}
