import { CdkScrollable } from '@angular/cdk/scrolling';
import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ScrollToTopFab } from './scroll-to-top-fab';

/** Stands in for the shell's content panel, the FAB's scroll container. */
@Component({
  imports: [CdkScrollable, ScrollToTopFab],
  template: '<div cdkScrollable><app-scroll-to-top-fab /></div>',
})
class Panel {}

let fixture: ComponentFixture<Panel>;

function render(): HTMLElement {
  TestBed.configureTestingModule({ imports: [Panel] });
  fixture = TestBed.createComponent(Panel);
  fixture.detectChanges();
  return fixture.nativeElement as HTMLElement;
}

/** Scrolls the panel and waits out the `ScrollDispatcher`'s 20ms audit time. */
async function scrollPanel(element: HTMLElement, top: number): Promise<void> {
  const panel = element.querySelector<HTMLElement>('[cdkScrollable]')!;
  panel.scrollTop = top;
  panel.dispatchEvent(new Event('scroll'));
  await new Promise((resolve) => setTimeout(resolve, 30));
  fixture.detectChanges();
}

describe('ScrollToTopFab', () => {
  it('stays hidden until the panel has scrolled past the threshold', async () => {
    const element = render();
    expect(element.querySelector('button')).toBeNull();

    await scrollPanel(element, 500);

    expect(element.querySelector('button')).not.toBeNull();
  });

  it('scrolls the panel back to the top on click', async () => {
    const element = render();
    await scrollPanel(element, 500);

    const panel = element.querySelector<HTMLElement>('[cdkScrollable]')!;
    const scrollTo = vi.fn();
    panel.scrollTo = scrollTo;
    element.querySelector('button')?.dispatchEvent(new Event('click'));

    expect(scrollTo).toHaveBeenCalledWith(expect.objectContaining({ top: 0, behavior: 'smooth' }));
  });
});
