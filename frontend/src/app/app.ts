/**
 * Root component — the app bar and the router outlet.
 *
 * The adaptive navigation (drawer / bottom bar, DESIGN §6.5) replaces this
 * plain header in M3; until there is more than one view, a title and the
 * theme control are the whole shell.
 */
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { RouterOutlet } from '@angular/router';

import { ThemeService } from './core/theme';

@Component({
  selector: 'app-root',
  imports: [MatButtonToggleModule, RouterOutlet],
  templateUrl: './app.html',
  styleUrl: './app.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class App {
  protected readonly title = signal('Film Rewatch');
  protected readonly theme = inject(ThemeService).preference;
}
