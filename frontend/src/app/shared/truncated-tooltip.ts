/**
 * Pairs with `matTooltip` on an ellipsis-truncated element: disables the
 * tooltip unless the text is actually clipped, so hovering an untruncated
 * title doesn't pop up a redundant repeat of what's already on screen.
 */
import { Directive, ElementRef, inject, afterNextRender } from '@angular/core';
import { MatTooltip } from '@angular/material/tooltip';

@Directive({
  selector: '[appTruncatedTooltip]',
  host: {
    '(window:resize)': 'updateDisabled()',
  },
})
export class TruncatedTooltipDirective {
  private readonly element = inject(ElementRef<HTMLElement>);
  private readonly tooltip = inject(MatTooltip, { self: true });

  constructor() {
    afterNextRender(() => this.updateDisabled());
  }

  protected updateDisabled(): void {
    const el = this.element.nativeElement;
    this.tooltip.disabled = el.scrollWidth <= el.clientWidth;
  }
}
