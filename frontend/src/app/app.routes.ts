/**
 * App routes — projected from the route registry (DESIGN §6.5, FR-EXT-02).
 *
 * This file is never edited to add a view; new views register themselves in
 * `core/routes.registry.ts` instead.
 */
import { Routes } from '@angular/router';

import { buildRoutes } from './core/route-registry';
import { ROUTE_REGISTRY } from './core/routes.registry';

export const routes: Routes = buildRoutes(ROUTE_REGISTRY);
