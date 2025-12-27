import { Routes } from '@angular/router';

export const routes: Routes = [
  // Redirect root to films
  {
    path: '',
    redirectTo: '/films',
    pathMatch: 'full'
  },

  // Feature: Films (Lazy Loaded)
  {
    path: 'films',
    loadChildren: () => import('./features/films/films.routes').then(m => m.FILMS_ROUTES),
  },
  {
    path: '**',
    redirectTo: '/films',
    pathMatch: 'full'
  }
];