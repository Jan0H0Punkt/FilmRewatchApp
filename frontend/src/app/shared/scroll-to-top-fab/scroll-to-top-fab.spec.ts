import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ScrollToTopFab } from './scroll-to-top-fab';

let fixture: ComponentFixture<ScrollToTopFab>;

function render(): HTMLElement {
  TestBed.configureTestingModule({ imports: [ScrollToTopFab] });
  fixture = TestBed.createComponent(ScrollToTopFab);
  fixture.detectChanges();
  return fixture.nativeElement as HTMLElement;
}

describe('ScrollToTopFab', () => {
  it('stays hidden until the page has scrolled past the threshold', () => {
    const element = render();
    expect(element.querySelector('button')).toBeNull();

    Object.defineProperty(window, 'scrollY', { configurable: true, value: 500 });
    window.dispatchEvent(new Event('scroll'));
    fixture.detectChanges();

    expect(element.querySelector('button')).not.toBeNull();
  });

  it('scrolls back to the top on click', () => {
    const element = render();
    Object.defineProperty(window, 'scrollY', { configurable: true, value: 500 });
    window.dispatchEvent(new Event('scroll'));
    fixture.detectChanges();

    const scrollTo = vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined);
    element.querySelector('button')?.dispatchEvent(new Event('click'));

    expect(scrollTo).toHaveBeenCalledWith({ top: 0, behavior: 'smooth' });
  });
});
