/**
 * A floating action button that appears once the page has scrolled down a
 * bit and jumps back to the top on click. Dumb by design (§6.1): it knows
 * nothing about the view it's placed in, just the scroll state of its
 * `cdkScrollable` ancestor — the shell's content panel (`app.html`).
 */
import { ScrollDispatcher } from '@angular/cdk/scrolling';
import { ChangeDetectionStrategy, Component, ElementRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
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
})
export class ScrollToTopFab {
  protected readonly visible = signal(false);
  private scroller: HTMLElement | undefined;

  constructor() {
    const host = inject<ElementRef<HTMLElement>>(ElementRef).nativeElement;
    // Not `ancestorScrolled()`: that resolves the ancestors once, up front,
    // when this host may not be attached yet. Other scrollables (a dialog's
    // content) are filtered out by containment instead.
    inject(ScrollDispatcher)
      .scrolled()
      .pipe(takeUntilDestroyed())
      .subscribe((target) => {
        const scroller = target?.getElementRef().nativeElement;
        if (!scroller?.contains(host)) return;
        this.scroller = scroller;
        this.visible.set(scroller.scrollTop > VISIBILITY_THRESHOLD_PX);
      });
  }

  protected scrollToTop(): void {
    this.scroller?.scrollTo({ top: 0, behavior: 'smooth' });
  }
}
