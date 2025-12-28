import { Component } from '@angular/core';
import { FormArray, FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { Film } from '../../services/film.service';
import { CommonModule } from '@angular/common';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatDividerModule } from '@angular/material/divider';
import { MatIcon } from "@angular/material/icon";

@Component({
  selector: 'mfa-film-add',
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatDividerModule,
    MatIcon
],
  templateUrl: './film-add.html',
  styleUrl: './film-add.scss',
})
export class FilmAdd {
  filmForm: FormGroup;

  constructor(private fb: FormBuilder) {
    this.filmForm = this.createForm();
  }

  private createForm(): FormGroup {
    return this.fb.group({
      title: ['', Validators.required],
      releaseYear: [null, [Validators.required, Validators.min(1888)]],
      posterUrl: [''],
      runtime: [null, [Validators.min(1)]],
      watchHistory: this.fb.array([])
    });
  }

  get watchHistory(): FormArray {
    return this.filmForm.get('watchHistory') as FormArray;
  }

  addWatchEntry(): void {
    this.watchHistory.push(this.createWatchEntry());
  }

  removeWatchEntry(index: number): void {
    this.watchHistory.removeAt(index);
  }

  private createWatchEntry(): FormGroup {
    return this.fb.group({
      watchedAt: [this.nowAsDateTimeLocal(), Validators.required],
      notes: ['']
    });
  }

  private nowAsDateTimeLocal(): string {
    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    return now.toISOString().slice(0, 16);
  }

  onSubmit(): void {
    if (this.filmForm.invalid) {
      this.filmForm.markAllAsTouched();
      return;
    }

    const film: Film = this.filmForm.value;

    console.log('Saving film:', film);

    // TODO:
    // 1. Save film
    // 2. Save watch history entries with filmId
    // 3. Navigate to film detail view
  }
}
