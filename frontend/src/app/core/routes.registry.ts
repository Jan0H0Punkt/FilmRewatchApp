/**
 * Route registry — the append-only list (DESIGN §6.5, FR-EXT-02).
 *
 * Views register themselves here by appending an entry. This is the single
 * place new routes are wired; `app.routes.ts` and `route-registry.ts` never
 * change. See `core/route-registry.ts` for the interface.
 */
import type { RouteRegistryEntry } from './route-registry';

const rewatch = (): Promise<typeof import('../views/rewatch/rewatch').Rewatch> =>
  import('../views/rewatch/rewatch').then((module) => module.Rewatch);

const library = (): Promise<typeof import('../views/library/library').Library> =>
  import('../views/library/library').then((module) => module.Library);

const filmDetail = (): Promise<typeof import('../views/film-detail/film-detail').FilmDetail> =>
  import('../views/film-detail/film-detail').then((module) => module.FilmDetail);

export const ROUTE_REGISTRY: readonly RouteRegistryEntry[] = [
  // Rewatch is the landing route: it is the primary discovery view (§6.5).
  // A redirect rather than a second mount, so `/` resolves to the same URL the
  // navigation links to and the active marker has one path to match.
  { path: '', redirectTo: 'rewatch' },
  { path: 'rewatch', title: 'Rewatch', loadComponent: rewatch, navIcon: 'replay', navLabel: 'Rewatch' },
  { path: 'library', title: 'Library', loadComponent: library, navIcon: 'video_library', navLabel: 'Library' },
  // Reached by selecting a film, never from the navigation (§6.5).
  { path: 'film/:id', title: 'Film', loadComponent: filmDetail },
];
