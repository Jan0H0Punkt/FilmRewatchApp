/** The join, the order guarantee, and the §6.3 optimistic removal. */
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';

import { FilmFacade } from '../film/facade';
import type { Film } from '../film/model';
import type { RewatchSuggestionDto } from './api';
import { RewatchApi } from './api';
import { RewatchFacade } from './facade';

function film(id: string, title: string, rating: number | null = 4): Film {
  return {
    id,
    primaryTitle: title,
    releaseYear: 1995,
    director: 'Michael Mann',
    runtimeMinutes: 170,
    genres: [],
    tags: [],
    posterImage: null,
    averageRating: rating,
    isFavorite: false,
    titles: [{ value: title, isPrimary: true, isOriginal: true }],
  };
}

function configure(films: readonly Film[], suggestions: readonly RewatchSuggestionDto[]) {
  const value = signal<readonly RewatchSuggestionDto[]>(suggestions);
  const apiStub = {
    list: {
      value,
      isLoading: signal(false),
      error: signal(undefined),
      reload: (): void => undefined,
    },
    removeFilm: (filmId: string): void =>
      value.update((suggestions) => suggestions.filter((s) => s.film_id !== filmId)),
  };
  TestBed.configureTestingModule({
    providers: [
      { provide: RewatchApi, useValue: apiStub },
      {
        provide: FilmFacade,
        useValue: { films: signal(films), isLoading: signal(false), error: signal(undefined) },
      },
    ],
  });
  return { facade: TestBed.inject(RewatchFacade), value };
}

describe('RewatchFacade', () => {
  it('joins each suggestion to its film', () => {
    const { facade } = configure([film('f1', 'Heat')], [{ film_id: 'f1', days_until_next_rewatch: -2 }]);

    expect(facade.cards().map((card) => [card.title, card.dueLabel])).toEqual([['Heat', 'Overdue by 2 days']]);
  });

  it('keeps the suggestion order even when the library is ordered differently', () => {
    // FR-RW-04: the client never re-sorts the algorithm's output.
    const { facade } = configure(
      [film('f1', 'Heat'), film('f2', 'Se7en')],
      [
        { film_id: 'f2', days_until_next_rewatch: -40 },
        { film_id: 'f1', days_until_next_rewatch: 0 },
      ],
    );

    expect(facade.cards().map((card) => card.title)).toEqual(['Se7en', 'Heat']);
  });

  it('skips a suggestion whose film the library does not hold', () => {
    const { facade } = configure(
      [film('f1', 'Heat')],
      [
        { film_id: 'ghost', days_until_next_rewatch: -9 },
        { film_id: 'f1', days_until_next_rewatch: 0 },
      ],
    );

    expect(facade.cards().map((card) => card.title)).toEqual(['Heat']);
  });

  it('removes exactly one film from the due-list on request', () => {
    const { facade } = configure(
      [film('f1', 'Heat'), film('f2', 'Se7en')],
      [
        { film_id: 'f1', days_until_next_rewatch: -1 },
        { film_id: 'f2', days_until_next_rewatch: -2 },
      ],
    );

    facade.removeFilm('f1');

    expect(facade.cards().map((card) => card.title)).toEqual(['Se7en']);
  });

  it('ignores a removal for a film that is not due', () => {
    const { facade } = configure([film('f1', 'Heat')], [{ film_id: 'f1', days_until_next_rewatch: 0 }]);

    facade.removeFilm('f2');

    expect(facade.cards()).toHaveLength(1);
  });

  it('has no cards for an empty due-list', () => {
    const { facade } = configure([film('f1', 'Heat')], []);

    expect(facade.cards()).toEqual([]);
  });
});
