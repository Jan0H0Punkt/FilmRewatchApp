/** The app shell: the branding, the theme control, and the §6.5 navigation. */
import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';

import { App } from './app';

async function render(routes: Parameters<typeof provideRouter>[0] = []): Promise<HTMLElement> {
  TestBed.configureTestingModule({
    imports: [App],
    providers: [provideRouter(routes)],
  });
  const fixture = TestBed.createComponent(App);
  await fixture.whenStable();
  return fixture.nativeElement as HTMLElement;
}

@Component({ template: '' })
class StubView {}

describe('App', () => {
  it('renders the app name as the sidebar branding', async () => {
    expect((await render()).querySelector('.app-nav__brand')?.textContent).toContain('Film Rewatch');
  });

  it("shows the active route's title in the app bar, not the app name", async () => {
    TestBed.configureTestingModule({
      imports: [App],
      providers: [provideRouter([{ path: 'rewatch', title: 'Rewatch', component: StubView }])],
    });
    // Navigated before the component is created, so `pageTitle`'s initial
    // `startWith` already sees it — no later `NavigationEnd` to wait out.
    await TestBed.inject(Router).navigateByUrl('/rewatch');
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();

    expect((fixture.nativeElement as HTMLElement).querySelector('h1')?.textContent).toBe('Rewatch');
  });

  it('renders both primary destinations in the navigation', async () => {
    const labels = (await render()).querySelectorAll('nav a .app-nav__label');

    expect([...labels].map((label) => label.textContent?.trim())).toEqual(['Rewatch', 'Library']);
  });

  it('renders each destination icon as a hidden ligature', async () => {
    const icons = (await render()).querySelectorAll('nav a mat-icon');

    expect([...icons].map((icon) => icon.textContent?.trim())).toEqual(['replay', 'video_library']);
    expect([...icons].every((icon) => icon.getAttribute('aria-hidden') === 'true')).toBe(true);
  });

  it('points each destination at its own route', async () => {
    const links = (await render()).querySelectorAll('nav a');

    expect([...links].map((link) => link.getAttribute('href'))).toEqual(['/rewatch', '/library']);
  });

  it('labels the navigation landmark', async () => {
    expect((await render()).querySelector('nav')?.getAttribute('aria-label')).toBe('Primary');
  });

  describe('back control (§6.5)', () => {
    // Fixture created before any navigation in every case here — unlike
    // `pageTitle` above, `NavigationHistoryService` has no synchronous
    // fallback for a route change that happened before it existed, so it
    // must already be subscribed when the navigation it needs to see fires.
    it('shows no back control on a primary navigation destination', async () => {
      TestBed.configureTestingModule({
        imports: [App],
        providers: [provideRouter([{ path: 'rewatch', title: 'Rewatch', component: StubView }])],
      });
      const fixture = TestBed.createComponent(App);
      await fixture.whenStable();
      await TestBed.inject(Router).navigateByUrl('/rewatch');
      await fixture.whenStable();

      expect((fixture.nativeElement as HTMLElement).querySelector('.app-bar__back')).toBeNull();
    });

    it('shows a back control on a contextual route, defaulting to the library route', async () => {
      TestBed.configureTestingModule({
        imports: [App],
        providers: [provideRouter([{ path: 'film/:id', title: 'Film', component: StubView }])],
      });
      const fixture = TestBed.createComponent(App);
      await fixture.whenStable();
      await TestBed.inject(Router).navigateByUrl('/film/f1');
      await fixture.whenStable();

      const back = (fixture.nativeElement as HTMLElement).querySelector('.app-bar__back');
      expect(back?.getAttribute('aria-label')).toBe('Back to Library');
      expect(back?.getAttribute('href')).toBe('/library');
    });

    it('points the back control at the last route visited before the contextual one', async () => {
      TestBed.configureTestingModule({
        imports: [App],
        providers: [
          provideRouter([
            { path: 'rewatch', title: 'Rewatch', component: StubView },
            { path: 'film/:id', title: 'Film', component: StubView },
          ]),
        ],
      });
      const fixture = TestBed.createComponent(App);
      await fixture.whenStable();
      const router = TestBed.inject(Router);

      await router.navigateByUrl('/rewatch');
      await fixture.whenStable();
      await router.navigateByUrl('/film/f1');
      await fixture.whenStable();

      const back = (fixture.nativeElement as HTMLElement).querySelector('.app-bar__back');
      expect(back?.getAttribute('aria-label')).toBe('Back to Rewatch');
      expect(back?.getAttribute('href')).toBe('/rewatch');
    });
  });
});
