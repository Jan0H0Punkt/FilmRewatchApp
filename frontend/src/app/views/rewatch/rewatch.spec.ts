/** The §7.1 card grid and its four states (FR-RW-06/07). */
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { RewatchFacade } from '../../domain/rewatch/facade';
import type { RewatchCardVm } from '../../domain/rewatch/model';
import { Rewatch } from './rewatch';

const HEAT: RewatchCardVm = {
  id: 'f1',
  title: 'Heat',
  year: 1995,
  posterImage: null,
  ratingStars: ['star', 'star', 'star', 'star', 'star_border'],
  ratingLabel: 'Average rating: 4.0 out of 5',
  isFavorite: true,
  dueLabel: 'Overdue by 5 days',
};

async function render(
  cards: readonly RewatchCardVm[],
  isLoading = false,
  error: unknown = undefined,
): Promise<HTMLElement> {
  // The favourite test renders twice; without the reset the second
  // `configureTestingModule` throws because a component already exists.
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    imports: [Rewatch],
    providers: [
      provideRouter([]),
      {
        provide: RewatchFacade,
        useValue: {
          cards: signal(cards),
          isLoading: signal(isLoading),
          error: signal(error),
          reload: (): void => undefined,
          onViewOpened: (): void => undefined,
        },
      },
    ],
  });
  const fixture = TestBed.createComponent(Rewatch);
  await fixture.whenStable();
  return fixture.nativeElement as HTMLElement;
}

describe('Rewatch view', () => {
  it('renders a card per due film', async () => {
    const element = await render([HEAT]);

    expect(element.querySelectorAll('.rewatch__card')).toHaveLength(1);
    expect(element.textContent).toContain('Heat');
    expect(element.textContent).toContain('1995');
    expect(element.textContent).toContain('Overdue by 5 days');
  });

  it('links each card to the film detail view', async () => {
    const element = await render([HEAT]);

    expect(element.querySelector('a')?.getAttribute('href')).toBe('/film/f1');
  });

  it('marks a favourite and leaves a non-favourite unmarked', async () => {
    const favourite = await render([HEAT]);
    expect(favourite.querySelector('.rewatch__favorite')).not.toBeNull();

    const plain = await render([{ ...HEAT, isFavorite: false }]);
    expect(plain.querySelector('.rewatch__favorite')).toBeNull();
  });

  it('shows a dash rather than empty stars for an unrated film', async () => {
    // FR-RAT-13: five empty stars would read as "rated zero".
    const element = await render([{ ...HEAT, ratingStars: null, ratingLabel: 'Not rated' }]);

    expect(element.querySelector('.rewatch__rating')?.textContent).toContain('—');
  });

  it('shows a loading state while the list is in flight', async () => {
    const element = await render([], true);

    expect(element.querySelector('[role="status"]')).not.toBeNull();
  });

  it('shows an empty state when nothing is due', async () => {
    // FR-RW-06: an empty due-list is a normal answer, not an error.
    const element = await render([]);

    expect(element.textContent).toContain('Nothing due right now');
    expect(element.querySelector('[role="alert"]')).toBeNull();
  });

  it('shows a non-blocking error without hiding the cards it already has', async () => {
    // FR-RW-07: the error is additive — the last successful run stays on screen.
    const element = await render([HEAT], false, new Error('boom'));

    expect(element.querySelector('[role="alert"]')).not.toBeNull();
    expect(element.querySelectorAll('.rewatch__card')).toHaveLength(1);
  });
});
