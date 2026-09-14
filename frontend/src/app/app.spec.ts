/** The app shell: the title, the theme control, and the §6.5 navigation. */
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { App } from './app';

async function render(): Promise<HTMLElement> {
  TestBed.configureTestingModule({
    imports: [App],
    providers: [provideRouter([])],
  });
  const fixture = TestBed.createComponent(App);
  await fixture.whenStable();
  return fixture.nativeElement as HTMLElement;
}

describe('App', () => {
  it('renders the app title', async () => {
    expect((await render()).querySelector('h1')?.textContent).toContain('Film Rewatch');
  });

  it('renders both primary destinations in the navigation', async () => {
    const links = (await render()).querySelectorAll('nav a');

    expect([...links].map((link) => link.textContent?.trim())).toEqual(['Rewatch', 'Library']);
  });

  it('points each destination at its own route', async () => {
    const links = (await render()).querySelectorAll('nav a');

    expect([...links].map((link) => link.getAttribute('href'))).toEqual(['/rewatch', '/library']);
  });

  it('labels the navigation landmark', async () => {
    expect((await render()).querySelector('nav')?.getAttribute('aria-label')).toBe('Primary');
  });
});
