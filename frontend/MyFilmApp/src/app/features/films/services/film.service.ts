import { Injectable } from '@angular/core';

export interface WatchEntry {
    date: string; // ISO date string
    rating: number; // 0-5
}

export interface Film {
    title: string;
    releaseYear: number;
    rating: number;
    posterUrl: string;
    runtime: number; // minutes
    watchHistory: WatchEntry[];
}

@Injectable({ providedIn: 'root' })
export class FilmService {
    private readonly films: Film[] = [
        {
            title: 'In the Mood for Love',
            releaseYear: 2000,
            rating: 5,
            posterUrl: 'https://a.ltrbxd.com/resized/sm/upload/g1/7l/2j/qk/tSRdvZY1waXrTeMqeLBmq9IRs08-0-2000-0-3000-crop.jpg?v=938633fc19',
            runtime: 98,
            watchHistory: [
                { date: '2018-06-15', rating: 5 },
                { date: '2019-08-20', rating: 5 },
                { date: '2021-04-10', rating: 4.5 },
                { date: '2022-09-05', rating: 5 },
                { date: '2023-12-12', rating: 5 },
                { date: '2024-03-22', rating: 4.5 },
                { date: '2025-06-01', rating: 5 },
                { date: '2026-07-15', rating: 5 },
                { date: '2027-08-20', rating: 5 },
                { date: '2028-09-30', rating: 4.5 },
                { date: '2029-10-10', rating: 5 },
                { date: '2030-11-25', rating: 5}
            ],
        },
        {
            title: 'Parasite',
            releaseYear: 2019,
            rating: 4.5,
            posterUrl: 'https://a.ltrbxd.com/resized/film-poster/4/2/6/4/0/6/426406-parasite-0-2000-0-3000-crop.jpg?v=8f5653f710',
            runtime: 132,
            watchHistory: [
                { date: '2022-11-10', rating: 4 },
            ],
        },
        {
            title: 'Hereditary',
            releaseYear: 2018,
            rating: 4,
            posterUrl: 'https://a.ltrbxd.com/resized/film-poster/4/2/4/3/4/8/424348-hereditary-0-2000-0-3000-crop.jpg?v=470e48b681',
            runtime: 127,
            watchHistory: [
                { date: '2023-10-31', rating: 4 },
            ],
        },
        {
            title: 'The Mummy Returns',
            releaseYear: 2001,
            rating: 3.5,
            posterUrl: 'https://a.ltrbxd.com/resized/film-poster/5/0/8/1/8/50818-the-mummy-returns-0-2000-0-3000-crop.jpg?v=57c66b4446',
            runtime: 130,
            watchHistory: [
                { date: '2021-06-05', rating: 3.5 },
            ],
        },
        {
            title: 'Little Miss Sunshine',
            releaseYear: 2006,
            rating: 3,
            posterUrl: 'https://a.ltrbxd.com/resized/sm/upload/h6/xm/om/q7/dOeM4R55TsAFBXCPNIDDMiJkePr-0-2000-0-3000-crop.jpg?v=09383296c6',
            runtime: 101,
            watchHistory: [
                { date: '2022-02-20', rating: 3 },
            ],
        },
        {
            title: 'Poor Things',
            releaseYear: 2023,
            rating: 2.5,
            posterUrl: 'https://a.ltrbxd.com/resized/film-poster/7/1/0/3/5/2/710352-poor-things-0-2000-0-3000-crop.jpg?v=a0f2ee9a0e',
            runtime: 135,
            watchHistory: [
                { date: '2024-05-12', rating: 2.5 },
            ],
        },
        {
            title: 'City of God',
            releaseYear: 2002,
            rating: 2,
            posterUrl: 'https://a.ltrbxd.com/resized/film-poster/5/1/5/2/3/51523-city-of-god-0-2000-0-3000-crop.jpg?v=7517ea94ce',
            runtime: 130,
            watchHistory: [
                { date: '2021-09-14', rating: 2 },
            ],
        },
        {
            title: 'Mad Max: Fury Road',
            releaseYear: 2015,
            rating: 1.5,
            posterUrl: 'https://a.ltrbxd.com/resized/film-poster/6/2/7/8/0/62780-mad-max-fury-road-0-2000-0-3000-crop.jpg?v=37c5424b1f',
            runtime: 120,
            watchHistory: [
                { date: '2022-07-30', rating: 1.5 },
            ],
        },
        {
            title: 'Past Lives',
            releaseYear: 2023,
            rating: 1,
            posterUrl: 'https://a.ltrbxd.com/resized/alternative-poster/5/9/1/0/5/3/p/nflfJ9IYNNMqPRHKGf9nbU6BsED-0-2000-0-3000-crop.jpg?v=748968c8cb',
            runtime: 105,
            watchHistory: [
                { date: '2024-04-18', rating: 1 },
            ],
        },
        {
            title: '12 Angry Men',
            releaseYear: 1957,
            rating: 0.5,
            posterUrl: 'https://a.ltrbxd.com/resized/film-poster/5/1/7/0/0/51700-12-angry-men-0-2000-0-3000-crop.jpg?v=b8aaf291a9',
            runtime: 96,
            watchHistory: [
                { date: '2021-12-01', rating: 0.5 },
            ],
        },
        {
            title: 'The Room',
            releaseYear: 2003,
            rating: 0,
            posterUrl: 'https://a.ltrbxd.com/resized/sm/upload/qq/yi/i3/dk/aUC39cFC2KO8CJ0EV0ijIJRr3PT-0-2000-0-3000-crop.jpg?v=95164ef310',
            runtime: 99,
            watchHistory: [
                { date: '2020-08-15', rating: 0 },
            ],
        },
        {
            title: 'The Godfather',
            releaseYear: 1972,
            rating: 5,
            posterUrl: 'https://a.ltrbxd.com/resized/film-poster/5/1/8/1/8/51818-the-godfather-0-2000-0-3000-crop.jpg?v=bca8b67402',
            runtime: 175,
            watchHistory: [
                { date: '2023-03-10', rating: 5 },
            ],
        },
        {
            title: 'Pulp Fiction',
            releaseYear: 1994,
            rating: 4.5,
            posterUrl: 'https://a.ltrbxd.com/resized/film-poster/5/1/4/4/4/51444-pulp-fiction-0-2000-0-3000-crop.jpg?v=dee19a8077',
            runtime: 154,
            watchHistory: [
                { date: '2022-12-25', rating: 4.5 },
            ],
        },
        {
            title: 'The Dark Knight',
            releaseYear: 2008,
            rating: 4,
            posterUrl: 'https://a.ltrbxd.com/resized/sm/upload/78/y5/zg/ej/oefdD26aey8GPdx7Rm45PNncJdU-0-2000-0-3000-crop.jpg?v=2d0ce4be25',
            runtime: 152,
            watchHistory: [
                { date: '2021-11-05', rating: 4 },
            ],
        },
        {
            title: 'Forrest Gump',
            releaseYear: 1994,
            rating: 3.5,
            posterUrl: 'https://a.ltrbxd.com/resized/film-poster/2/7/0/4/2704-forrest-gump-0-2000-0-3000-crop.jpg?v=173bc04cf0',
            runtime: 142,
            watchHistory: [
                { date: '2020-05-20', rating: 3.5 },
            ],
        },
        {
            title: 'The Shawshank Redemption',
            releaseYear: 1994,
            rating: 3,
            posterUrl: 'https://a.ltrbxd.com/resized/sm/upload/7l/hn/46/uz/zGINvGjdlO6TJRu9wESQvWlOKVT-0-2000-0-3000-crop.jpg?v=8736d1c395',
            runtime: 142,
            watchHistory: [
                { date: '2019-09-10', rating: 3 },
            ],
        },
    ];

    getFilms(): Film[] {
        return this.films;
    }

    getFilm(index: number): Film {
        return this.films[index];
    }
}
