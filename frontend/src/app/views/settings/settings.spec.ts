/** The rewatch-share slider and the FR-RW-09 pace field: shown values, save-on-commit, and the save-error state. */
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';

import { SettingsFacade } from '../../domain/settings/facade';
import { Settings } from './settings';

function render(rewatchShare: number | null, error: string | null = null, watchIntervalDays: number | null = null) {
  const setRewatchShare = vi.fn();
  const setWatchIntervalDays = vi.fn();
  TestBed.configureTestingModule({
    imports: [Settings],
    providers: [
      {
        provide: SettingsFacade,
        useValue: {
          rewatchShare: signal(rewatchShare),
          watchIntervalDays: signal(watchIntervalDays),
          error: signal(error),
          onViewOpened: (): void => undefined,
          setRewatchShare,
          setWatchIntervalDays,
        },
      },
    ],
  });
  const fixture = TestBed.createComponent(Settings);
  fixture.detectChanges();
  const element = fixture.nativeElement as HTMLElement;
  const thumb = element.querySelector<HTMLInputElement>('input[matSliderThumb]');
  if (thumb === null) throw new Error('slider thumb not rendered');
  const pace = element.querySelector<HTMLInputElement>('#watch-interval');
  if (pace === null) throw new Error('pace input not rendered');
  return { element, thumb, setRewatchShare, pace, setWatchIntervalDays, fixture };
}

describe('Settings view', () => {
  it('shows the stored percentage', () => {
    expect(render(30).thumb.value).toBe('30');
  });

  it('shows Off as 100%, which is equally uncapped', () => {
    expect(render(null).thumb.value).toBe('100');
  });

  it('labels the ends new watches and rewatches', () => {
    expect(render(30).element.querySelector('.setting__ends')?.textContent).toMatch(/New watches.*Rewatches/s);
  });

  it('names the share in the header, and 100% as no limit', () => {
    expect(render(30).element.querySelector('.setting__value')?.textContent).toBe('30% rewatches');
    TestBed.resetTestingModule();
    expect(render(null).element.querySelector('.setting__value')?.textContent).toBe('No limit');
  });

  it('saves the released value via the facade', () => {
    const { thumb, setRewatchShare } = render(null);

    thumb.value = '40';
    thumb.dispatchEvent(new Event('change'));

    expect(setRewatchShare).toHaveBeenCalledWith(40);
  });

  it('shows the facade error when a save fails', () => {
    const { element } = render(null, 'The rewatch share could not be saved.');

    expect(element.querySelector('[role="alert"]')?.textContent).toContain('The rewatch share could not be saved.');
  });

  describe('watch pace (FR-RW-09)', () => {
    function commit(pace: HTMLInputElement, value: string): void {
      pace.value = value;
      pace.dispatchEvent(new Event('change'));
    }

    it('shows the stored pace, labelled, with the films-per-year hint', () => {
      const { element, pace } = render(null, null, 7);

      expect(pace.value).toBe('7');
      expect(element.querySelector('label[for="watch-interval"]')?.textContent).toContain('Watch 1 film every');
      expect(element.textContent).toContain('≈ 52 films per year');
    });

    it('shows an empty field and no hint when Off', () => {
      const { element, pace } = render(null);

      expect(pace.value).toBe('');
      expect(element.textContent).not.toContain('films per year');
    });

    it('saves a whole number on change', () => {
      const { pace, setWatchIntervalDays } = render(null);

      commit(pace, '5');

      expect(setWatchIntervalDays).toHaveBeenCalledWith(5);
    });

    it('saves null for an emptied field', () => {
      const { pace, setWatchIntervalDays } = render(null, null, 7);

      commit(pace, '');

      expect(setWatchIntervalDays).toHaveBeenCalledWith(null);
    });

    it('rejects a non-integer or a value below 1 without saving, and says so', () => {
      const { element, pace, setWatchIntervalDays, fixture } = render(null);

      commit(pace, '2.5');
      commit(pace, '0');
      fixture.detectChanges();

      expect(setWatchIntervalDays).not.toHaveBeenCalled();
      expect(element.querySelector('[role="alert"]')?.textContent).toContain('whole number');
      expect(pace.getAttribute('aria-invalid')).toBe('true');
    });
  });
});
