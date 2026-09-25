/** GET mapping, the optimistic PUT write and its rollback, and refetch on reopen. */
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { environment } from '../../../environments/environment';
import { SettingsFacade } from './facade';

const URL = `${environment.apiBaseUrl}/settings`;

/** Same microtask-settling need as `StatsFacade`'s spec — `httpResource`'s loader is async. */
async function settle(): Promise<void> {
  await Promise.resolve();
  await Promise.resolve();
  TestBed.tick();
}

describe('SettingsFacade', () => {
  let facade: SettingsFacade;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    facade = TestBed.inject(SettingsFacade);
    http = TestBed.inject(HttpTestingController);
    TestBed.tick();
  });

  afterEach(() => http.verify());

  it('maps the loaded row to the domain shape', async () => {
    http.expectOne(URL).flush({ rewatch_share: 30 });
    await settle();

    expect(facade.rewatchShare()).toBe(30);
  });

  it('reads as Off (null) while the row has not loaded yet', async () => {
    const req = http.expectOne(URL);
    expect(facade.rewatchShare()).toBeNull();

    req.flush({ rewatch_share: 30 });
    await settle();
  });

  it("reads as Off (null) when the load fails — the Rewatch view's cap fails open on this", async () => {
    http.expectOne(URL).flush('down', { status: 500, statusText: 'Server Error' });
    await settle();

    expect(facade.rewatchShare()).toBeNull();
  });

  it('applies a save immediately, before the response lands', async () => {
    http.expectOne(URL).flush({ rewatch_share: null });
    await settle();

    facade.setRewatchShare(40);

    expect(facade.rewatchShare()).toBe(40);
    http.expectOne({ url: URL, method: 'PUT' }).flush({ rewatch_share: 40 });
  });

  it('rolls back to the previous value and sets the error on a failed save', async () => {
    http.expectOne(URL).flush({ rewatch_share: 20 });
    await settle();

    facade.setRewatchShare(70);
    expect(facade.rewatchShare()).toBe(70);

    http.expectOne({ url: URL, method: 'PUT' }).flush('down', { status: 500, statusText: 'Server Error' });
    await settle();

    expect(facade.rewatchShare()).toBe(20);
    expect(facade.error()).toBeTruthy();
  });

  it('clears a previous error at the start of the next save', async () => {
    http.expectOne(URL).flush({ rewatch_share: null });
    await settle();

    facade.setRewatchShare(10);
    http.expectOne({ url: URL, method: 'PUT' }).flush('down', { status: 500, statusText: 'Server Error' });
    await settle();
    expect(facade.error()).toBeTruthy();

    facade.setRewatchShare(20);
    expect(facade.error()).toBeNull();
    http.expectOne({ url: URL, method: 'PUT' }).flush({ rewatch_share: 20 });
  });

  it('refetches when the view is opened again', async () => {
    facade.onViewOpened();
    http.expectOne(URL).flush({ rewatch_share: null });
    await settle();

    facade.onViewOpened();
    await settle();
    http.expectOne(URL).flush({ rewatch_share: null });
  });
});
