/**
 * Root component (M0 PR7) — renders the placeholder shell and the router
 * outlet. The adaptive navigation (drawer / bottom bar, DESIGN §6.5) replaces
 * the placeholder in M3.
 */
import { Component, signal } from '@angular/core';
import { RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {
  protected readonly title = signal('Film Rewatch');
}
