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
  },

  {
    path: 'add',
    loadComponent: () => import('./views/film-add/film-add')
      .then(m => m.FilmAdd),
    title: 'Add New Film'
  },

  // /films/:id - Film details
  {
    path: ':id',
    loadComponent: () => import('./views/film-details/film-details')
      .then(m => m.FilmDetails),
    title: 'Film Details'
  },
  {
    path: '**',
    redirectTo: '/films',
    pathMatch: 'full'
  }
];