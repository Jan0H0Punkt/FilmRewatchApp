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
});
