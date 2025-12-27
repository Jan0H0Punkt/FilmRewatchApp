import { Component } from '@angular/core';
import { MatCard } from '@angular/material/card';
import { MatIcon } from '@angular/material/icon';
import { RatingStarsPipe } from '../../pipes/rating-stars.pipe';
import { FilmService, Film } from '../../services/film.service';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'mfa-film-list',
  imports: [MatCard, MatIcon, RatingStarsPipe, RouterLink],
  templateUrl: './film-list.html',
  styleUrl: './film-list.scss',
})
export class FilmList {
  protected readonly films: Array<Film>;

  constructor(private readonly filmService: FilmService) {
    this.films = this.filmService.getFilms();
  }
}

