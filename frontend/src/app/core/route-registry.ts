/**
 * Route registry infrastructure (DESIGN §6.5, FR-EXT-02) — M0 PR7.
 *
 * The interface and builder function. Views register themselves in
 * `routes.registry.ts` (the append-only data file), not here.
 */
import type { Type } from '@angular/core';
import type { Routes } from '@angular/router';

/** One routed view's registration (§6.5). */
export interface RouteRegistryEntry {
  /** URL path, e.g. `rewatch` or `film/:id`. */
  readonly path: string;
  /** Page title shown for the view. */
  readonly title: string;
  /** Lazy loader for the routed standalone component. */
  readonly loadComponent: () => Promise<Type<unknown>>;
}

/** Projects the registry into the `Routes` array the Angular router consumes. */
export function buildRoutes(registry: readonly RouteRegistryEntry[]): Routes {
  return registry.map(({ path, title, loadComponent }) => ({
    path,
    title,
    loadComponent,
  }));
}
