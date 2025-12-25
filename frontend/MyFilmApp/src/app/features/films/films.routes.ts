import { Routes } from '@angular/router';

export const FILMS_ROUTES: Routes = [
  // Default route for /films
  {
    path: '',
    redirectTo: 'list',
    pathMatch: 'full'
  },

  // /films/list - List all films
  {
    path: 'list',
    loadComponent: () => import('./views/film-list/film-list')
      .then(m => m.FilmList),
    title: 'My Films'
  }
];