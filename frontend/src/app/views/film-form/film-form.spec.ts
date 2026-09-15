/**
 * The Add Film form (`open work/library-view/add-film-via-search.md`,
 * work item 2): the `?title=` prefill, required-field validation gating
 * submit, a valid submit calling `FilmFacade.create` and navigating to the
 * Library, and the 409 duplicate backstop.
 */
import { ENTER } from '@angular/cdk/keycodes';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideNativeDateAdapter } from '@angular/material/core';
import { Router, provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';

import { FilmFacade } from '../../domain/film/facade';
import type { Film, FilmCreateInput } from '../../domain/film/model';
import { GenreFacade } from '../../domain/genre/facade';
import { TagFacade } from '../../domain/tag/facade';
import { FilmForm } from './film-form';

/** Matches a route in the test router config without pulling in a real view. */
@Component({ selector: 'app-blank', template: '' })
class BlankComponent {}

const CREATED: Film = {
  id: 'new-film',
  primaryTitle: 'Heat',
  releaseYear: 1995,
  director: 'Michael Mann',
  runtimeMinutes: 170,
  genres: ['Crime'],
  tags: ['heist'],
  posterImage: null,
  averageRating: 4,
  isFavorite: false,
  titles: [{ value: 'Heat', isPrimary: true, isOriginal: false }],
};

/** Stands in for `FilmFacade` — the facade under test is `FilmForm`, not this one. */
function stubFilmFacade() {
  return { create: vi.fn().mockReturnValue(of(CREATED)) };
}

/** Stands in for `TagFacade`/`GenreFacade` so the autocompletes have a vocabulary without HTTP. */
function stubLabelFacade(names: readonly string[]) {
  return { names: signal(names), reload: vi.fn() };
}

let currentFixture: ComponentFixture<FilmForm>;

async function render(
  filmFacade: ReturnType<typeof stubFilmFacade> = stubFilmFacade(),
  title = '',
): Promise<HTMLElement> {
  TestBed.configureTestingModule({
    imports: [FilmForm],
    providers: [
      provideRouter([{ path: 'library', component: BlankComponent }]),
      provideNativeDateAdapter(),
      { provide: FilmFacade, useValue: filmFacade },
      { provide: TagFacade, useValue: stubLabelFacade(['heist', 'neo-noir']) },
      { provide: GenreFacade, useValue: stubLabelFacade(['Crime', 'Drama']) },
    ],
  });
  currentFixture = TestBed.createComponent(FilmForm);
  currentFixture.componentRef.setInput('title', title);
  await currentFixture.whenStable();
  return currentFixture.nativeElement as HTMLElement;
}

async function settle(): Promise<void> {
  await currentFixture.whenStable();
}

function setValue(element: HTMLElement, selector: string, value: string): void {
  const input = element.querySelector<HTMLInputElement>(selector)!;
  input.value = value;
  input.dispatchEvent(new Event('input'));
}

/** Enter on a chip input — Material's chip input reads `keyCode`, which jsdom leaves at 0. */
function pressEnter(input: HTMLInputElement): void {
  const event = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true });
  Object.defineProperty(event, 'keyCode', { get: () => ENTER });
  input.dispatchEvent(event);
}

/** Opens an editable-chips row's edit mode, types `value`, and commits it with Enter. */
async function addChip(element: HTMLElement, rowClass: string, value: string): Promise<void> {
  element.querySelector<HTMLButtonElement>(`.${rowClass} .editable-chips__toggle`)!.click();
  await settle();
  const input = element.querySelector<HTMLInputElement>(`.${rowClass} input`)!;
  input.value = value;
  input.dispatchEvent(new Event('input'));
  pressEnter(input);
  await settle();
}

/** Fills every required field except whichever the caller omits from `skip`. */
async function fillRequiredFields(element: HTMLElement, skip: ReadonlySet<string> = new Set()): Promise<void> {
  if (!skip.has('title')) setValue(element, '.film-form__title input', 'Heat');
  if (!skip.has('year')) setValue(element, '.film-form__year input', '1995');
  if (!skip.has('director')) setValue(element, '.film-form__director input', 'Michael Mann');
  if (!skip.has('runtime')) setValue(element, '.film-form__runtime input', '170');
  await settle();
  if (!skip.has('genres')) await addChip(element, 'film-form__genres', 'Crime');
  if (!skip.has('tags')) await addChip(element, 'film-form__tags', 'heist');
}

describe('FilmForm', () => {
  afterEach(() => TestBed.resetTestingModule());

  it('prefills the title from the ?title= query param', async () => {
    const element = await render(stubFilmFacade(), 'Heat');

    expect(element.querySelector<HTMLInputElement>('.film-form__title input')?.value).toBe('Heat');
  });

  it('disables submit until every required field is filled', async () => {
    const element = await render();

    expect(element.querySelector<HTMLButtonElement>('button[type="submit"]')?.disabled).toBe(true);

    await fillRequiredFields(element);

    expect(element.querySelector<HTMLButtonElement>('button[type="submit"]')?.disabled).toBe(false);
  });

  it('stays disabled while a required field — genres — is still missing', async () => {
    const element = await render();

    await fillRequiredFields(element, new Set(['genres']));

    expect(element.querySelector<HTMLButtonElement>('button[type="submit"]')?.disabled).toBe(true);
  });

  it('submits the mapped payload and navigates to the Library on success', async () => {
    const filmFacade = stubFilmFacade();
    const element = await render(filmFacade);
    const router = TestBed.inject(Router);
    const navigateSpy = vi.spyOn(router, 'navigateByUrl');
    await fillRequiredFields(element);

    element.querySelector<HTMLButtonElement>('button[type="submit"]')!.click();
    await settle();

    expect(filmFacade.create).toHaveBeenCalledWith(
      expect.objectContaining<Partial<FilmCreateInput>>({
        primaryTitle: 'Heat',
        releaseYear: 1995,
        director: 'Michael Mann',
        runtimeMinutes: 170,
        genres: ['Crime'],
        tags: ['heist'],
        rating: null,
      }),
    );
    expect(navigateSpy).toHaveBeenCalledWith('/library');
  });

  it('blocks submission and names the colliding film on a 409 DUPLICATE_FILM response', async () => {
    const filmFacade = stubFilmFacade();
    filmFacade.create.mockReturnValue(
      throwError(
        () =>
          new HttpErrorResponse({
            status: 409,
            error: { error: { code: 'DUPLICATE_FILM', message: 'Duplicate of existing film "Heat" — id f1.' } },
          }),
      ),
    );
    const element = await render(filmFacade);
    const router = TestBed.inject(Router);
    const navigateSpy = vi.spyOn(router, 'navigateByUrl');
    await fillRequiredFields(element);

    element.querySelector<HTMLButtonElement>('button[type="submit"]')!.click();
    await settle();

    expect(element.querySelector('[role="alert"]')?.textContent).toContain('Heat');
    expect(navigateSpy).not.toHaveBeenCalled();
  });
});
