/** The assign dialog's title search: matches any title, not just the primary one (FR-LBX-06). */
import { TestBed } from '@angular/core/testing';
import { MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';

import { FilmFacade } from '../../domain/film/facade';
import type { Film } from '../../domain/film/model';
import { AssignDialog, type AssignDialogData } from './assign-dialog';

function film(id: string, primaryTitle: string, altTitle?: string): Film {
  return {
    id,
    primaryTitle,
    releaseYear: 1995,
    director: 'Someone',
    runtimeMinutes: 100,
    genres: [],
    tags: [],
    posterImage: null,
    letterboxdUrl: null,
    averageRating: null,
    isFavorite: false,
    owned: false,
    titles: altTitle
      ? [
          { value: primaryTitle, isPrimary: true, isOriginal: false },
          { value: altTitle, isPrimary: false, isOriginal: false },
        ]
      : [{ value: primaryTitle, isPrimary: true, isOriginal: false }],
  };
}

async function render(films: readonly Film[], data: AssignDialogData = { filmTitle: '' }) {
  TestBed.configureTestingModule({
    imports: [AssignDialog],
    providers: [
      { provide: FilmFacade, useValue: { films: () => films } },
      { provide: MatDialogRef, useValue: { close: vi.fn() } },
      { provide: MAT_DIALOG_DATA, useValue: data },
    ],
  });
  const fixture = TestBed.createComponent(AssignDialog);
  await fixture.whenStable();
  return fixture.componentInstance;
}

describe('AssignDialog', () => {
  it('matches a film by an alternative title', async () => {
    const heat = film('f1', 'Heat', 'Le Ultime 36 Ore');
    const component = await render([heat, film('f2', 'Se7en')]);

    component['search'].set('ultime');

    expect(component['matches']()).toEqual([heat]);
  });

  it('does not match a title that is absent from every title', async () => {
    const component = await render([film('f1', 'Heat', 'Le Ultime 36 Ore'), film('f2', 'Se7en')]);

    component['search'].set('gojira');

    expect(component['matches']()).toEqual([]);
  });
});
