/**
 * Route registry — the append-only list (DESIGN §6.5, FR-EXT-02) — M0 PR7.
 *
 * Views register themselves here by appending an entry. This is the single
 * place M3+ edits to wire new routes; `app.routes.ts` and `route-registry.ts`
 * never change. See `core/route-registry.ts` for the interface.
 */
import type { RouteRegistryEntry } from './route-registry';

export const ROUTE_REGISTRY: readonly RouteRegistryEntry[] = [];
