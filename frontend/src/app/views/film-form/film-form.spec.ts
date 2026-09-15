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
import { Router, provideRouter, withComponentInputBinding } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
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

/** Types `value` into an editable-chips row (already open — `startExpanded`) and commits it with Enter. */
async function addChip(element: HTMLElement, rowClass: string, value: string): Promise<void> {
  const input = element.querySelector<HTMLInputElement>(`.${rowClass} input`)!;
  input.value = value;
  input.dispatchEvent(new Event('input'));
  pressEnter(input);
  await settle();
}

function titleRowElements(element: HTMLElement): readonly HTMLElement[] {
  return [...element.querySelectorAll<HTMLElement>('.film-form__title-row')];
}

function titleValueInput(element: HTMLElement, index = 0): HTMLInputElement {
  return titleRowElements(element)[index]!.querySelector<HTMLInputElement>('.film-form__title-value input')!;
}

function primaryCheckbox(element: HTMLElement, index = 0): HTMLInputElement {
  return titleRowElements(element)[index]!.querySelector<HTMLInputElement>(
    '.film-form__title-primary input[type="checkbox"]',
  )!;
}

function originalCheckbox(element: HTMLElement, index = 0): HTMLInputElement {
  return titleRowElements(element)[index]!.querySelector<HTMLInputElement>(
    '.film-form__title-original input[type="checkbox"]',
  )!;
}

async function addTitleRow(element: HTMLElement): Promise<void> {
  element.querySelector<HTMLButtonElement>('.film-form__title-add')!.click();
  await settle();
}

/** Fills every required field except whichever the caller omits from `skip`. */
async function fillRequiredFields(element: HTMLElement, skip: ReadonlySet<string> = new Set()): Promise<void> {
  if (!skip.has('title')) setValue(element, '.film-form__title-value input', 'Heat');
  if (!skip.has('year')) setValue(element, '.film-form__year input', '1995');
  if (!skip.has('director')) setValue(element, '.film-form__director input', 'Michael Mann');
  if (!skip.has('runtime')) setValue(element, '.film-form__runtime input', '170');
  await settle();
  if (!skip.has('genres')) await addChip(element, 'film-form__genres', 'Crime');
  if (!skip.has('tags')) await addChip(element, 'film-form__tags', 'heist');
}

describe('FilmForm', () => {
  afterEach(() => TestBed.resetTestingModule());

  it('renders an empty title field, not the literal text "undefined", when the route carries no ?title= at all', async () => {
    // Reached directly (no Library search first) — e.g. a bookmark, or the
    // Library's empty-state "Add your first film" link, which routes to
    // `films/new` with no query params. `withComponentInputBinding()` does
    // not call `setInput` for a query param key absent from the URL, so this
    // exercises the real gap the manual `render()` helper's explicit
    // `setInput('title', '')` above always papers over.
    TestBed.configureTestingModule({
      providers: [
        provideRouter(
          [{ path: 'films/new', loadComponent: () => Promise.resolve(FilmForm) }],
          withComponentInputBinding(),
        ),
        provideNativeDateAdapter(),
        { provide: FilmFacade, useValue: stubFilmFacade() },
        { provide: TagFacade, useValue: stubLabelFacade([]) },
        { provide: GenreFacade, useValue: stubLabelFacade([]) },
      ],
    });
    const harness = await RouterTestingHarness.create('/films/new');

    const titleInput = harness.routeNativeElement?.querySelector<HTMLInputElement>('.film-form__title-value input');

    expect(titleInput?.value).toBe('');
  });

  it('prefills the title from the ?title= query param', async () => {
    const element = await render(stubFilmFacade(), 'Heat');

    expect(titleValueInput(element).value).toBe('Heat');
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
        titles: [{ value: 'Heat', isPrimary: true, isOriginal: false }],
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

  describe('titles (REQ §4.1)', () => {
    it('starts with a single row, Primary checked and disabled (a lone title has no other to defer to), with no remove button', async () => {
      const element = await render();

      expect(titleRowElements(element)).toHaveLength(1);
      expect(primaryCheckbox(element, 0).checked).toBe(true);
      expect(primaryCheckbox(element, 0).disabled).toBe(true);
      expect(element.querySelector('.film-form__title-remove')).toBeNull();
    });

    it('adds a removable row when Add another title is clicked, its Primary checkbox already disabled by the first row’s', async () => {
      const element = await render();

      await addTitleRow(element);

      expect(titleRowElements(element)).toHaveLength(2);
      expect(element.querySelectorAll('.film-form__title-remove')).toHaveLength(2);
      expect(primaryCheckbox(element, 1).disabled).toBe(true);
    });

    it('removes a row, dropping back to one row with no remove button', async () => {
      const element = await render();
      await addTitleRow(element);

      element.querySelectorAll<HTMLButtonElement>('.film-form__title-remove')[1]!.click();
      await settle();

      expect(titleRowElements(element)).toHaveLength(1);
      expect(element.querySelector('.film-form__title-remove')).toBeNull();
    });

    it('disables every other row’s Primary checkbox once one is checked, including a row added afterward', async () => {
      const element = await render();
      await addTitleRow(element);
      primaryCheckbox(element, 0).click(); // uncheck row 0's default so row 1 starts the mutual exclusion from a clean slate
      await settle();

      primaryCheckbox(element, 1).click();
      await settle();
      expect(primaryCheckbox(element, 0).disabled).toBe(true);

      await addTitleRow(element);
      expect(primaryCheckbox(element, 2).disabled).toBe(true);
    });

    it('re-enables every row’s Primary checkbox once the checked one is unchecked', async () => {
      const element = await render();
      await addTitleRow(element); // row 1 starts disabled — row 0's default Primary is still checked

      primaryCheckbox(element, 0).click(); // uncheck it
      await settle();

      expect(primaryCheckbox(element, 1).disabled).toBe(false);
    });

    it('keeps Original mutually exclusive independently of Primary', async () => {
      const element = await render();
      await addTitleRow(element);
      primaryCheckbox(element, 0).click(); // uncheck the default so this test isolates Original's own exclusion
      await settle();

      originalCheckbox(element, 0).click();
      await settle();

      expect(originalCheckbox(element, 1).disabled).toBe(true);
      expect(primaryCheckbox(element, 1).disabled).toBe(false);
    });

    it('ignores a click on the single title’s disabled Primary checkbox — it cannot be unchecked', async () => {
      const element = await render();
      await fillRequiredFields(element);

      primaryCheckbox(element, 0).click();
      await settle();

      expect(primaryCheckbox(element, 0).checked).toBe(true);
      expect(element.querySelector<HTMLButtonElement>('button[type="submit"]')?.disabled).toBe(false);
    });

    it('enables the first row’s Primary checkbox again once a second title exists', async () => {
      const element = await render();

      await addTitleRow(element);

      expect(primaryCheckbox(element, 0).disabled).toBe(false);
    });

    it('blocks submit once there is more than one title unless exactly one is marked Primary', async () => {
      const element = await render();
      await fillRequiredFields(element);
      await addTitleRow(element);
      titleValueInput(element, 1).value = 'Hitze';
      titleValueInput(element, 1).dispatchEvent(new Event('input'));
      await settle();
      // Row 0's default Primary already satisfies "exactly one".
      expect(element.querySelector<HTMLButtonElement>('button[type="submit"]')?.disabled).toBe(false);

      primaryCheckbox(element, 0).click(); // uncheck it — now nothing is marked Primary
      await settle();

      expect(element.querySelector<HTMLButtonElement>('button[type="submit"]')?.disabled).toBe(true);
    });

    it('sends every row flagged as checked, in row order', async () => {
      const filmFacade = stubFilmFacade();
      const element = await render(filmFacade);
      await fillRequiredFields(element);
      await addTitleRow(element);
      titleValueInput(element, 1).value = 'Hitze';
      titleValueInput(element, 1).dispatchEvent(new Event('input'));
      await settle();
      originalCheckbox(element, 1).click();
      await settle();

      element.querySelector<HTMLButtonElement>('button[type="submit"]')!.click();
      await settle();

      expect(filmFacade.create).toHaveBeenCalledWith(
        expect.objectContaining<Partial<FilmCreateInput>>({
          titles: [
            { value: 'Heat', isPrimary: true, isOriginal: false },
            { value: 'Hitze', isPrimary: false, isOriginal: true },
          ],
        }),
      );
    });
  });
});
