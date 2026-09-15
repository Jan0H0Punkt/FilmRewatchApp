/** Film Detail's back control reads `backTarget`/`backLabel` from this service — see `navigation-history.ts`. */
import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';

import { NavigationHistoryService } from './navigation-history';

@Component({ selector: 'app-blank', template: '' })
class BlankComponent {}

function setup(): { service: NavigationHistoryService; router: Router } {
  TestBed.configureTestingModule({
    providers: [
      provideRouter([
        { path: 'rewatch', component: BlankComponent },
        { path: 'library', component: BlankComponent },
        { path: 'film/:id', component: BlankComponent },
        { path: '**', component: BlankComponent },
      ]),
    ],
  });
  return { service: TestBed.inject(NavigationHistoryService), router: TestBed.inject(Router) };
}

describe('NavigationHistoryService', () => {
  afterEach(() => TestBed.resetTestingModule());

  it('defaults to the library when nothing has been visited', () => {
    const { service } = setup();

    expect(service.backTarget()).toBe('/library');
    expect(service.backLabel()).toBe('Library');
  });

  it('remembers a visited route and its registry title', async () => {
    const { service, router } = setup();

    await router.navigateByUrl('/rewatch');

    expect(service.backTarget()).toBe('/rewatch');
    expect(service.backLabel()).toBe('Rewatch');
  });

  it('does not let a film detail route overwrite the remembered one', async () => {
    const { service, router } = setup();

    await router.navigateByUrl('/rewatch');
    await router.navigateByUrl('/film/f1');

    expect(service.backTarget()).toBe('/rewatch');
  });

  it('falls back to the Library label for an unrecognised URL, without throwing', async () => {
    const { service, router } = setup();

    await router.navigateByUrl('/somewhere-unknown');

    expect(() => service.backLabel()).not.toThrow();
    expect(service.backLabel()).toBe('Library');
  });
});
