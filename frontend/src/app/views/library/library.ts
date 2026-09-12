/**
 * The Library view (REQ §7.2) — the whole film library as a result list.
 *
 * Search, filtering, and the Add Film action are the rest of §7.2 and are not
 * built yet; this is the unfiltered list the backend's `GET /films` serves.
 * Per §6.1 the view calls the facade only and holds no rules — the ViewModel
 * shaping (the parts of a film this list actually prints) lives here.
 */
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatChipsModule } from '@angular/material/chips';
import { MatIconModule } from '@angular/material/icon';

import { FilmFacade } from '../../domain/film/facade';

/** One row of the result list (§7.2 "Film Result Item"). */
interface FilmRowVm {
  readonly id: string;
  readonly title: string;
  readonly posterImage: string | null;
  /** Year, director, and runtime as the one subtitle line the row prints. */
  readonly subtitle: string;
  readonly genres: readonly string[];
  readonly tags: readonly string[];
  readonly rating: string;
  readonly isFavorite: boolean;
}

@Component({
  selector: 'app-library',
  imports: [MatButtonModule, MatChipsModule, MatIconModule],
  templateUrl: './library.html',
  styleUrl: './library.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Library {
  private readonly films = inject(FilmFacade);

  protected readonly isLoading = this.films.isLoading;
  protected readonly error = this.films.error;

  protected readonly rows = computed<readonly FilmRowVm[]>(() =>
    this.films.films().map((film) => ({
      id: film.id,
      title: film.primaryTitle,
      posterImage: film.posterImage,
      subtitle: [String(film.releaseYear), film.director, `${film.runtimeMinutes} min`].join(' · '),
      genres: film.genres,
      tags: film.tags,
      rating: film.averageRating.toFixed(1),
      isFavorite: film.isFavorite,
    })),
  );

  protected reload(): void {
    this.films.reload();
  }
}
