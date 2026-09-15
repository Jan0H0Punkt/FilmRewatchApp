import { TestBed } from '@angular/core/testing';

import { ThemeService } from './theme';

describe('ThemeService', () => {
  beforeEach(() => localStorage.clear());

  it('cycles light -> dark -> auto -> light on each call', () => {
    const service = TestBed.inject(ThemeService);
    service.preference.set('light');

    service.cycle();
    expect(service.preference()).toBe('dark');

    service.cycle();
    expect(service.preference()).toBe('auto');

    service.cycle();
    expect(service.preference()).toBe('light');
  });
});
