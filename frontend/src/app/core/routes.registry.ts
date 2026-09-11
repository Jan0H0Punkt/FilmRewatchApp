/**
 * Route registry — the append-only list (DESIGN §6.5, FR-EXT-02).
 *
 * Views register themselves here by appending an entry. This is the single
 * place new routes are wired; `app.routes.ts` and `route-registry.ts` never
 * change. See `core/route-registry.ts` for the interface.
 */
import type { RouteRegistryEntry } from './route-registry';

const library = (): Promise<typeof import('../views/library/library').Library> =>
  import('../views/library/library').then((module) => module.Library);

export const ROUTE_REGISTRY: readonly RouteRegistryEntry[] = [
  // The Library is also the landing route until the Rewatch view exists.
  { path: '', title: 'Library', loadComponent: library },
  { path: 'library', title: 'Library', loadComponent: library },
];
