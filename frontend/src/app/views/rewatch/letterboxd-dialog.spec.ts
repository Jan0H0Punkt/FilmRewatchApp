/** The Rewatch card's add-link dialog: save/cancel, the disabled-when-empty guard, and the error path. */
import { TestBed } from '@angular/core/testing';
import { MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import { of, throwError } from 'rxjs';

import { FilmFacade } from '../../domain/film/facade';
import { LetterboxdDialog, type LetterboxdDialogData } from './letterboxd-dialog';

function stubFilmFacade() {
  return { update: vi.fn().mockReturnValue(of(undefined)) };
}

function stubDialogRef() {
  return { close: vi.fn() };
}

async function render(
  filmFacade: ReturnType<typeof stubFilmFacade>,
  dialogRef: ReturnType<typeof stubDialogRef> = stubDialogRef(),
  data: LetterboxdDialogData = { filmId: 'f1' },
): Promise<{ element: HTMLElement; fixture: ReturnType<typeof TestBed.createComponent<LetterboxdDialog>> }> {
  TestBed.configureTestingModule({
    imports: [LetterboxdDialog],
    providers: [
      { provide: FilmFacade, useValue: filmFacade },
      { provide: MatDialogRef, useValue: dialogRef },
      { provide: MAT_DIALOG_DATA, useValue: data },
    ],
  });
  const fixture = TestBed.createComponent(LetterboxdDialog);
  await fixture.whenStable();
  return { element: fixture.nativeElement as HTMLElement, fixture };
}

describe('LetterboxdDialog', () => {
  it('disables Save until a URL is typed', async () => {
    const { element } = await render(stubFilmFacade());

    expect(element.querySelector<HTMLButtonElement>('button[matButton="filled"]')?.disabled).toBe(true);
  });

  it('saves the trimmed URL via FilmFacade.update and closes on success', async () => {
    const filmFacade = stubFilmFacade();
    const dialogRef = stubDialogRef();
    const { element, fixture } = await render(filmFacade, dialogRef, { filmId: 'f1' });

    const input = element.querySelector<HTMLInputElement>('input')!;
    input.value = '  https://boxd.it/aaaa  ';
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    element.querySelector<HTMLButtonElement>('button[matButton="filled"]')!.click();

    expect(filmFacade.update).toHaveBeenCalledWith('f1', { letterboxdUrl: 'https://boxd.it/aaaa' });
    expect(dialogRef.close).toHaveBeenCalled();
  });

  it('shows an error and leaves the dialog open when the save fails', async () => {
    const filmFacade = { update: vi.fn().mockReturnValue(throwError(() => new Error('boom'))) };
    const dialogRef = stubDialogRef();
    const { element, fixture } = await render(filmFacade, dialogRef);

    const input = element.querySelector<HTMLInputElement>('input')!;
    input.value = 'https://boxd.it/aaaa';
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    element.querySelector<HTMLButtonElement>('button[matButton="filled"]')!.click();
    fixture.detectChanges();

    expect(element.querySelector('[role="alert"]')?.textContent).toContain('could not be saved');
    expect(dialogRef.close).not.toHaveBeenCalled();
  });
});
