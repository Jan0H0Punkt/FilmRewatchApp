/** Picks the film a Letterboxd entry's watch goes to (FR-LBX-06), searching the cached library by title. */
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { MatAutocompleteModule } from '@angular/material/autocomplete';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';

import { FilmFacade } from '../../domain/film/facade';
import type { Film } from '../../domain/film/model';

export interface AssignDialogData {
  readonly filmTitle: string;
}

const MAX_OPTIONS = 20;

@Component({
  selector: 'app-assign-dialog',
  imports: [MatAutocompleteModule, MatButtonModule, MatDialogModule, MatFormFieldModule, MatInputModule],
  template: `
    <h2 matDialogTitle>Assign “{{ data.filmTitle }}”</h2>
    <mat-dialog-content>
      <mat-form-field class="assign__field">
        <mat-label>Film</mat-label>
        <input #query matInput [value]="data.filmTitle" [matAutocomplete]="films" (input)="search.set(query.value)" />
        <mat-autocomplete #films="matAutocomplete" (optionSelected)="choose($event.option.value)">
          @for (film of matches(); track film.id) {
            <mat-option [value]="film">{{ film.primaryTitle }} ({{ film.releaseYear }})</mat-option>
          }
        </mat-autocomplete>
      </mat-form-field>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button matButton type="button" [mat-dialog-close]="undefined">Cancel</button>
    </mat-dialog-actions>
  `,
  styles: '.assign__field { width: 100%; }',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AssignDialog {
  protected readonly data = inject<AssignDialogData>(MAT_DIALOG_DATA);
  private readonly dialogRef = inject<MatDialogRef<AssignDialog, string>>(MatDialogRef);
  private readonly films = inject(FilmFacade).films;

  protected readonly search = signal(this.data.filmTitle);
  protected readonly matches = computed<readonly Film[]>(() => {
    const query = this.search().trim().toLowerCase();
    return this.films()
      .filter((film) => film.titles.some((title) => title.value.toLowerCase().includes(query)))
      .slice(0, MAX_OPTIONS);
  });

  protected choose(film: Film): void {
    this.dialogRef.close(film.id);
  }
}
