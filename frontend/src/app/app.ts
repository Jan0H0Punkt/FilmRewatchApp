/**
 * Root component — the app bar, the §6.5 navigation, and the router outlet.
 *
 * The navigation adapts by viewport in CSS alone (`app.scss`): a bottom bar on
 * a phone, a permanent left sidebar from 900px up. The design names
 * `mat-sidenav mode="side"` for the wide case, but a drawer that is always open
 * and never toggles is a static sidebar — the container, the breakpoint
 * observer and the `mode` binding would all render the same thing.
 */
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatIconModule } from '@angular/material/icon';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { navDestinations } from './core/route-registry';
import { ROUTE_REGISTRY } from './core/routes.registry';
import { ThemeService } from './core/theme';

@Component({
  selector: 'app-root',
  imports: [MatButtonToggleModule, MatIconModule, RouterLink, RouterLinkActive, RouterOutlet],
  templateUrl: './app.html',
  styleUrl: './app.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class App {
  protected readonly title = signal('Film Rewatch');
  protected readonly theme = inject(ThemeService).preference;
  /** Derived from the registry, so registering a route stays the one wiring point (FR-EXT-02). */
  protected readonly destinations = navDestinations(ROUTE_REGISTRY);
}
