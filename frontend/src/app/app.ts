/**
 * Root component — the app bar, the §6.5 navigation, and the router outlet.
 *
 * The navigation adapts by viewport in CSS alone (`app.scss`): a bottom bar on
 * a phone, a permanent left sidebar from 900px up. The design names
 * `mat-sidenav mode="side"` for the wide case, but a drawer that is always open
 * and never toggles is a static sidebar — the container, the breakpoint
 * observer and the `mode` binding would all render the same thing.
 */
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter, map, startWith } from 'rxjs';

import { NavigationHistoryService } from './core/navigation-history';
import { navDestinations } from './core/route-registry';
import { ROUTE_REGISTRY } from './core/routes.registry';
import { ThemeService, type ThemePreference } from './core/theme';

/** One icon per preference (§theme) — the button shows the active one, not a menu of all three. */
const THEME_ICONS: Record<ThemePreference, string> = {
  light: 'light_mode',
  dark: 'dark_mode',
  auto: 'brightness_auto',
};

/** `ThemeService.cycle()`'s own order — mirrored here so the tooltip can name what a click does. */
const NEXT_THEME: Record<ThemePreference, ThemePreference> = {
  light: 'dark',
  dark: 'auto',
  auto: 'light',
};

@Component({
  selector: 'app-root',
  imports: [MatButtonModule, MatIconModule, MatTooltipModule, RouterLink, RouterLinkActive, RouterOutlet],
  templateUrl: './app.html',
  styleUrl: './app.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class App {
  /** App branding, shown in the sidebar — the app bar itself carries the current page's title instead. */
  protected readonly appName = 'Film Rewatch';

  private readonly router = inject(Router);

  /**
   * The active leaf route's `title` (`routes.registry.ts`), read straight off
   * the route snapshot rather than back from the `Title` service: the
   * router's default title strategy writes `document.title` in a microtask
   * *after* `NavigationEnd` fires, so reading it back at that point would
   * race and see the previous page's title.
   */
  protected readonly pageTitle = toSignal(
    this.router.events.pipe(
      filter((event): event is NavigationEnd => event instanceof NavigationEnd),
      map(() => this.router.routerState.snapshot.root.firstChild?.title ?? ''),
      startWith(this.router.routerState.snapshot.root.firstChild?.title ?? ''),
    ),
    { requireSync: true },
  );

  /** The app bar's own back control (§6.5) — shown only on a contextual route like Film Detail. */
  private readonly navigationHistory = inject(NavigationHistoryService);
  protected readonly showBackControl = this.navigationHistory.showBackControl;
  protected readonly backTarget = this.navigationHistory.backTarget;
  protected readonly backLabel = this.navigationHistory.backLabel;

  private readonly themeService = inject(ThemeService);
  protected readonly theme = this.themeService.preference;
  protected readonly themeIcon = computed(() => THEME_ICONS[this.theme()]);
  protected readonly themeTooltip = computed(() => `Switch to ${NEXT_THEME[this.theme()]} theme`);

  protected cycleTheme(): void {
    this.themeService.cycle();
  }

  /** Derived from the registry, so registering a route stays the one wiring point (FR-EXT-02). */
  protected readonly destinations = navDestinations(ROUTE_REGISTRY);
}
