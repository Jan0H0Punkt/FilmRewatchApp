/** Nav destinations are derived from the registry, so registering a route stays the single wiring point (FR-EXT-02). */
import { navDestinations, type RouteRegistryEntry } from './route-registry';
import { ROUTE_REGISTRY } from './routes.registry';

const load = (): Promise<never> => Promise.reject(new Error('not loaded in tests'));

describe('navDestinations', () => {
  it('includes only entries carrying both nav fields', () => {
    const registry: readonly RouteRegistryEntry[] = [
      { path: 'a', title: 'A', loadComponent: load, navIcon: 'star', navLabel: 'Alpha' },
      { path: 'b', title: 'B', loadComponent: load },
    ];

    expect(navDestinations(registry)).toEqual([{ path: 'a', icon: 'star', label: 'Alpha' }]);
  });

  it('excludes a redirect entry, which mounts no component', () => {
    const registry: readonly RouteRegistryEntry[] = [
      { path: '', title: 'A', redirectTo: 'a' },
      { path: 'a', title: 'A', loadComponent: load, navIcon: 'star', navLabel: 'Alpha' },
    ];

    expect(navDestinations(registry).map((item) => item.path)).toEqual(['a']);
  });

  it('keeps the registry order', () => {
    const registry: readonly RouteRegistryEntry[] = [
      { path: 'a', title: 'A', loadComponent: load, navIcon: 'i', navLabel: 'A' },
      { path: 'b', title: 'B', loadComponent: load, navIcon: 'i', navLabel: 'B' },
    ];

    expect(navDestinations(registry).map((item) => item.path)).toEqual(['a', 'b']);
  });
});

describe('ROUTE_REGISTRY', () => {
  it('exposes exactly the two §6.5 primary destinations', () => {
    expect(navDestinations(ROUTE_REGISTRY).map((item) => item.label)).toEqual(['Rewatch', 'Library']);
  });

  it('never exposes the contextual film detail route', () => {
    expect(navDestinations(ROUTE_REGISTRY).map((item) => item.path)).not.toContain('film/:id');
  });

  it('redirects the root path to the Rewatch view', () => {
    // A redirect, not a second mount: `/` must resolve to the URL the
    // navigation links to, or it would mark no destination active.
    expect(ROUTE_REGISTRY.find((entry) => entry.path === '')?.redirectTo).toBe('rewatch');
  });
});
