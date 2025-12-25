import { Component } from '@angular/core';
import { MatCard } from '@angular/material/card';
import { MatIcon } from '@angular/material/icon';
import { RatingStarsPipe } from '../../pipes/rating-stars.pipe';

interface Film {
  title: string;
  releaseYear: number;
  rating: number;
  posterUrl: string;
}

@Component({
  selector: 'mfa-film-list',
  imports: [MatCard, MatIcon, RatingStarsPipe],
  templateUrl: './film-list.html',
  styleUrl: './film-list.scss',
})
export class FilmList {
  protected readonly films: Array<Film> = [
    {
      title: 'In the Mood for Love',
      releaseYear: 2000,
      rating: 5,
      posterUrl: 'https://a.ltrbxd.com/resized/sm/upload/g1/7l/2j/qk/tSRdvZY1waXrTeMqeLBmq9IRs08-0-2000-0-3000-crop.jpg?v=938633fc19',
    },
    {
      title: 'Parasite',
      releaseYear: 2019,
      rating: 4.5,
      posterUrl: 'https://a.ltrbxd.com/resized/film-poster/4/2/6/4/0/6/426406-parasite-0-2000-0-3000-crop.jpg?v=8f5653f710',
    },
    {
      title: 'Hereditary',
      releaseYear: 2018,
      rating: 4,
      posterUrl: 'https://a.ltrbxd.com/resized/film-poster/4/2/4/3/4/8/424348-hereditary-0-2000-0-3000-crop.jpg?v=470e48b681',
    },
    {
      title: 'The Mummy Returns',
      releaseYear: 2001,
      rating: 3.5,
      posterUrl: 'https://a.ltrbxd.com/resized/film-poster/5/0/8/1/8/50818-the-mummy-returns-0-2000-0-3000-crop.jpg?v=57c66b4446',
    },
    {
      title: 'Little Miss Sunshine',
      releaseYear: 2006,
      rating: 3,
      posterUrl: 'https://a.ltrbxd.com/resized/sm/upload/h6/xm/om/q7/dOeM4R55TsAFBXCPNIDDMiJkePr-0-2000-0-3000-crop.jpg?v=09383296c6',
    },
    {
      title: 'Poor Things',
      releaseYear: 2023,
      rating: 2.5,
      posterUrl: 'https://a.ltrbxd.com/resized/film-poster/7/1/0/3/5/2/710352-poor-things-0-2000-0-3000-crop.jpg?v=a0f2ee9a0e',
    },
    {
      title: 'City of God',
      releaseYear: 2002,
      rating: 2,
      posterUrl: 'https://a.ltrbxd.com/resized/film-poster/5/1/5/2/3/51523-city-of-god-0-2000-0-3000-crop.jpg?v=7517ea94ce',
    },
    {
      title: 'Mad Max: Fury Road',
      releaseYear: 2015,
      rating: 1.5,
      posterUrl: 'https://a.ltrbxd.com/resized/film-poster/6/2/7/8/0/62780-mad-max-fury-road-0-2000-0-3000-crop.jpg?v=37c5424b1f',
    },
    {
      title: 'Past Lives',
      releaseYear: 2023,
      rating: 1,
      posterUrl: 'https://a.ltrbxd.com/resized/alternative-poster/5/9/1/0/5/3/p/nflfJ9IYNNMqPRHKGf9nbU6BsED-0-2000-0-3000-crop.jpg?v=748968c8cb',
    },
    {
      title: '12 Angry Men',
      releaseYear: 1957,
      rating: 0.5,
      posterUrl: 'https://a.ltrbxd.com/resized/film-poster/5/1/7/0/0/51700-12-angry-men-0-2000-0-3000-crop.jpg?v=b8aaf291a9',
    }
  ];

}

