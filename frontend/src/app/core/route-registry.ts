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
  /** Page title shown for the view. Not read for a `redirectTo` entry — the browser navigates on to the target route's own title. */
  readonly title?: string;
  /** Lazy loader for the routed standalone component. */
  readonly loadComponent?: () => Promise<Type<unknown>>;
  /**
   * Material icon for the navigation element (§6.5). Present together with
   * `navLabel` on exactly the primary destinations — an entry carrying both is
   * what makes it one, so `film/:id` (contextual) needs no opt-out.
   */
  readonly navIcon?: string;
  /** Navigation label, shown beside `navIcon`. */
  readonly navLabel?: string;
  /**
   * Set instead of `loadComponent` to make this path a redirect — the landing
   * route (§6.5) points at the Rewatch view this way rather than mounting the
   * component a second time, which would leave `/` matching no navigation
   * entry and so marking none of them active.
   */
  readonly redirectTo?: string;
}

/** Projects the registry into the `Routes` array the Angular router consumes. */
export function buildRoutes(registry: readonly RouteRegistryEntry[]): Routes {
  return registry.map(({ path, title, loadComponent, redirectTo }) =>
    redirectTo === undefined
      ? { path, title, loadComponent }
      : // `pathMatch: 'full'` so an empty path redirects only when it is the
        // whole URL, not as a prefix of every other route.
        { path, redirectTo, pathMatch: 'full' as const },
  );
}

/** One entry of the navigation element (§6.5). */
export interface NavDestination {
  readonly path: string;
  readonly icon: string;
  readonly label: string;
}

/** The registry's primary navigation destinations, in registry order (§6.5, FR-EXT-02). */
export function navDestinations(registry: readonly RouteRegistryEntry[]): readonly NavDestination[] {
  return registry.flatMap((entry) =>
    entry.navIcon !== undefined && entry.navLabel !== undefined
      ? [{ path: entry.path, icon: entry.navIcon, label: entry.navLabel }]
      : [],
  );
}
