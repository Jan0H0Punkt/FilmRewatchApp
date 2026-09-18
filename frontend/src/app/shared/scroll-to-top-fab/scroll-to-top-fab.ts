/**
 * A floating action button that appears once the page has scrolled down a
 * bit and jumps back to the top on click. Dumb by design (§6.1): it knows
 * nothing about the view it's placed in, just `window` scroll state.
 */
import { ChangeDetectionStrategy, Component, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

/** Below this offset the button stays hidden — the top is already one scroll away. */
const VISIBILITY_THRESHOLD_PX = 400;

@Component({
  selector: 'app-scroll-to-top-fab',
  imports: [MatButtonModule, MatIconModule],
  templateUrl: './scroll-to-top-fab.html',
  styleUrl: './scroll-to-top-fab.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    '(window:scroll)': 'onWindowScroll()',
  },
})
export class ScrollToTopFab {
  protected readonly visible = signal(false);

  protected onWindowScroll(): void {
    this.visible.set(window.scrollY > VISIBILITY_THRESHOLD_PX);
  }

  protected scrollToTop(): void {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
}
