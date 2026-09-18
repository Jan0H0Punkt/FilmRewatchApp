/**
 * Remembers the last route visited before Film Detail, so the app bar's back
 * control (§6.5) returns to wherever the user came from — Rewatch or
 * Library — instead of a hardcoded destination. Falls back to `/library`
 * for a deep link, a PWA cold start, or a reload while already on the
 * detail view, none of which leave a prior route to remember. Also decides
 * whether that control shows at all (`showBackControl`): only on a
 * contextual route, never on a primary navigation destination.
 */
import { Injectable, computed, inject, signal } from '@angular/core';
import { NavigationEnd, Router } from '@angular/router';
import { filter } from 'rxjs';

import { ROUTE_REGISTRY } from './routes.registry';

const FALLBACK_TARGET = '/library';
const FALLBACK_LABEL = 'Library';

/** Film Detail is reached contextually, never as a navigation destination (§6.5) — remembering it would make back a no-op. */
function isDetailRoute(url: string): boolean {
  return url.startsWith('/film/');
}

@Injectable({ providedIn: 'root' })
export class NavigationHistoryService {
  private readonly lastNonDetailUrl = signal<string | null>(null);
  private readonly currentUrl = signal('');

  constructor() {
    inject(Router)
      .events.pipe(filter((event): event is NavigationEnd => event instanceof NavigationEnd))
      .subscribe((event) => {
        this.currentUrl.set(event.urlAfterRedirects);
        if (!isDetailRoute(event.urlAfterRedirects)) this.lastNonDetailUrl.set(event.urlAfterRedirects);
      });
  }

  /** Whether the app bar's own back control (§6.5) should show — only on a contextual route like Film Detail. */
  readonly showBackControl = computed(() => isDetailRoute(this.currentUrl()));

  /** The remembered URL, or `/library` when nothing has been visited yet. */
  readonly backTarget = computed(() => this.lastNonDetailUrl() ?? FALLBACK_TARGET);

  /**
   * `backTarget`'s human name, looked up in `ROUTE_REGISTRY` (FR-EXT-02) —
   * the single wiring point, not a second path→name mapping. Registry paths
   * carry no leading slash, hence the strip.
   */
  readonly backLabel = computed(
    () => ROUTE_REGISTRY.find((entry) => entry.path === this.backTarget().replace(/^\//, ''))?.title ?? FALLBACK_LABEL,
  );
}
