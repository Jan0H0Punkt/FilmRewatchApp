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
    http.expectOne(URL).flush({ rewatch_share: 30, watch_interval_days: null });
    await settle();

    expect(facade.rewatchShare()).toBe(30);
  });

  it('maps the watch pace and sends the unchanged share when only the pace is saved', async () => {
    http.expectOne(URL).flush({ rewatch_share: 30, watch_interval_days: 7 });
    await settle();
    expect(facade.watchIntervalDays()).toBe(7);

    facade.setWatchIntervalDays(3);

    expect(facade.watchIntervalDays()).toBe(3);
    const put = http.expectOne({ url: URL, method: 'PUT' });
    expect(put.request.body).toEqual({ rewatch_share: 30, watch_interval_days: 3 });
    put.flush({ rewatch_share: 30, watch_interval_days: 3 });
  });

  it('sends the unchanged pace when only the share is saved', async () => {
    http.expectOne(URL).flush({ rewatch_share: 30, watch_interval_days: 7 });
    await settle();

    facade.setRewatchShare(50);

    const put = http.expectOne({ url: URL, method: 'PUT' });
    expect(put.request.body).toEqual({ rewatch_share: 50, watch_interval_days: 7 });
    put.flush({ rewatch_share: 50, watch_interval_days: 7 });
  });

  it('rolls back a failed pace save with the pace error', async () => {
    http.expectOne(URL).flush({ rewatch_share: 30, watch_interval_days: 7 });
    await settle();

    facade.setWatchIntervalDays(null);
    http.expectOne({ url: URL, method: 'PUT' }).flush('down', { status: 500, statusText: 'Server Error' });
    await settle();

    expect(facade.watchIntervalDays()).toBe(7);
    expect(facade.error()).toBe('The watch pace could not be saved.');
  });

  it('reads as Off (null) while the row has not loaded yet', async () => {
    const req = http.expectOne(URL);
    expect(facade.rewatchShare()).toBeNull();

    req.flush({ rewatch_share: 30, watch_interval_days: null });
    await settle();
  });

  it("reads as Off (null) when the load fails — the Rewatch view's cap fails open on this", async () => {
    http.expectOne(URL).flush('down', { status: 500, statusText: 'Server Error' });
    await settle();

    expect(facade.rewatchShare()).toBeNull();
  });

  it('applies a save immediately, before the response lands', async () => {
    http.expectOne(URL).flush({ rewatch_share: null, watch_interval_days: null });
    await settle();

    facade.setRewatchShare(40);

    expect(facade.rewatchShare()).toBe(40);
    http.expectOne({ url: URL, method: 'PUT' }).flush({ rewatch_share: 40, watch_interval_days: null });
  });

  it('rolls back to the previous value and sets the error on a failed save', async () => {
    http.expectOne(URL).flush({ rewatch_share: 20, watch_interval_days: null });
    await settle();

    facade.setRewatchShare(70);
    expect(facade.rewatchShare()).toBe(70);

    http.expectOne({ url: URL, method: 'PUT' }).flush('down', { status: 500, statusText: 'Server Error' });
    await settle();

    expect(facade.rewatchShare()).toBe(20);
    expect(facade.error()).toBeTruthy();
  });

  it('clears a previous error at the start of the next save', async () => {
    http.expectOne(URL).flush({ rewatch_share: null, watch_interval_days: null });
    await settle();

    facade.setRewatchShare(10);
    http.expectOne({ url: URL, method: 'PUT' }).flush('down', { status: 500, statusText: 'Server Error' });
    await settle();
    expect(facade.error()).toBeTruthy();

    facade.setRewatchShare(20);
    expect(facade.error()).toBeNull();
    http.expectOne({ url: URL, method: 'PUT' }).flush({ rewatch_share: 20, watch_interval_days: null });
  });

  it('refetches when the view is opened again', async () => {
    facade.onViewOpened();
    http.expectOne(URL).flush({ rewatch_share: null, watch_interval_days: null });
    await settle();

    facade.onViewOpened();
    await settle();
    http.expectOne(URL).flush({ rewatch_share: null, watch_interval_days: null });
  });
});
