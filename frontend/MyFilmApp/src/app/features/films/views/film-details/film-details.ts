import { Component, computed, inject, input, OnInit } from '@angular/core';
import { MatIcon } from '@angular/material/icon';
import { RatingStarsPipe } from '../../pipes/rating-stars.pipe';
import { FilmService } from '../../services/film.service';

@Component({
  selector: 'mfa-film-details',
  imports: [ MatIcon, RatingStarsPipe],
  templateUrl: './film-details.html',
  styleUrl: './film-details.scss',
})
export class FilmDetails {
  private readonly filmService = inject(FilmService);

  id = input.required<number>();
  film = computed(() => this.filmService.getFilm(this.id()));
  endTime = computed(() => this.film() ? this.calcEndTime(this.film().runtime) : '');

  private calcEndTime(runtime: number): string {
    const end = new Date(Date.now() + (runtime * 60 * 1000));
    return end.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
}
