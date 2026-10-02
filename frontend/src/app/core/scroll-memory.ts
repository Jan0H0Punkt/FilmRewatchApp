/**
 * Remembers each view's last scroll offset for the current app session, so
 * navigating away and back restores where the user left off. In-memory only
 * (a plain `Map` on a root-provided singleton) — a reload or fresh app start
 * clears it naturally, without needing to distinguish that from any other reset.
 */
import { ScrollDispatcher } from '@angular/cdk/scrolling';
import { DestroyRef, effect, ElementRef, inject, Injectable, type Signal, type WritableSignal } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class ScrollMemoryService {
  private readonly positions = new Map<string, number>();
  private readonly renderLimits = new Map<string, number>();
  private readonly scrollDispatcher = inject(ScrollDispatcher);

  /**
   * Restores `key`'s offset once `isLoading` turns false — so it lands in the
   * real list, not the loading state — and saves it again when the calling
   * view is destroyed. Call from a view's constructor (it `inject`s).
   *
   * The offset is that of the shell's content panel, the view's `cdkScrollable`
   * ancestor (`app.html`). It is looked up on restore and kept: by the time the
   * view is destroyed, its host is already detached and has no ancestors.
   *
   * A view that renders its list incrementally passes its `renderLimit`: the
   * remembered value is set synchronously (before first render) so the restored
   * offset is not clamped by a too-short list, and the current one is saved on destroy.
   */
  remember(key: string, isLoading: Signal<boolean>, renderLimit?: WritableSignal<number>): void {
    const host = inject<ElementRef<HTMLElement>>(ElementRef);
    const savedLimit = this.renderLimits.get(key);
    if (renderLimit && savedLimit !== undefined) renderLimit.set(savedLimit);
    let scroller: HTMLElement | undefined;

    effect(() => {
      if (isLoading() || scroller) return;
      scroller = this.scrollDispatcher.getAncestorScrollContainers(host)[0]?.getElementRef().nativeElement;
      scroller?.scrollTo({ top: this.positions.get(key) ?? 0 });
    });

    inject(DestroyRef).onDestroy(() => {
      if (scroller) this.positions.set(key, scroller.scrollTop);
      if (renderLimit) this.renderLimits.set(key, renderLimit());
    });
  }
}
