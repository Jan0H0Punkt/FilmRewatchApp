/** The rewatch-share slider: the shown value, save-on-release, and the save-error state. */
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';

import { SettingsFacade } from '../../domain/settings/facade';
import { Settings } from './settings';

function render(rewatchShare: number | null, error: string | null = null) {
  const setRewatchShare = vi.fn();
  TestBed.configureTestingModule({
    imports: [Settings],
    providers: [
      {
        provide: SettingsFacade,
        useValue: {
          rewatchShare: signal(rewatchShare),
          error: signal(error),
          onViewOpened: (): void => undefined,
          setRewatchShare,
        },
      },
    ],
  });
  const fixture = TestBed.createComponent(Settings);
  fixture.detectChanges();
  const element = fixture.nativeElement as HTMLElement;
  const thumb = element.querySelector<HTMLInputElement>('input[matSliderThumb]');
  if (thumb === null) throw new Error('slider thumb not rendered');
  return { element, thumb, setRewatchShare };
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
});
