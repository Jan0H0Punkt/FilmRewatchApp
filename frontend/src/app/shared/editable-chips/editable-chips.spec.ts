/**
 * Editable chip row: the keyboard path of the orderable rows (genres), which
 * shares its `moveItemInArray` core with the drag path a unit test cannot
 * gesture. Bounds and the modifier requirement are the parts that break
 * silently, so they are what is pinned here.
 */
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { EditableChips } from './editable-chips';

const GENRES = ['Action', 'Comedy', 'Adventure', 'Comic'];

let fixture: ComponentFixture<EditableChips>;

async function render(values: readonly string[], orderable: boolean, startExpanded = false): Promise<HTMLElement> {
  TestBed.configureTestingModule({ imports: [EditableChips] });
  fixture = TestBed.createComponent(EditableChips);
  fixture.componentRef.setInput('label', 'Genres');
  fixture.componentRef.setInput('itemNoun', 'genre');
  fixture.componentRef.setInput('values', values);
  fixture.componentRef.setInput('suggestions', []);
  fixture.componentRef.setInput('orderable', orderable);
  fixture.componentRef.setInput('startExpanded', startExpanded);
  await fixture.whenStable();
  return fixture.nativeElement as HTMLElement;
}

/** The emitted list from the one `changed` emission, or `null` if it stayed silent. */
function emissionFrom(
  element: HTMLElement,
  chipIndex: number,
  key: string,
  modifier: 'ctrl' | 'meta' | 'none',
): readonly string[] | null {
  let emitted: readonly string[] | null = null;
  fixture.componentInstance.changed.subscribe((next) => (emitted = next));
  const chip = element.querySelectorAll('mat-chip')[chipIndex];
  chip.dispatchEvent(
    new KeyboardEvent('keydown', {
      key,
      bubbles: true,
      ctrlKey: modifier === 'ctrl',
      metaKey: modifier === 'meta',
    }),
  );
  return emitted;
}

describe('EditableChips', () => {
  afterEach(() => TestBed.resetTestingModule());

  it('moves a chip one slot right on Ctrl+ArrowRight', async () => {
    const element = await render(GENRES, true);
    expect(emissionFrom(element, 1, 'ArrowRight', 'ctrl')).toEqual(['Action', 'Adventure', 'Comedy', 'Comic']);
  });

  it('moves a chip one slot left on Cmd+ArrowLeft', async () => {
    const element = await render(GENRES, true);
    expect(emissionFrom(element, 2, 'ArrowLeft', 'meta')).toEqual(['Action', 'Adventure', 'Comedy', 'Comic']);
  });

  it('stays silent at either end of the row', async () => {
    const element = await render(GENRES, true);
    expect(emissionFrom(element, 0, 'ArrowLeft', 'ctrl')).toBeNull();
    expect(emissionFrom(element, GENRES.length - 1, 'ArrowRight', 'ctrl')).toBeNull();
  });

  it('ignores an unmodified arrow, leaving it to the chip row’s own focus movement', async () => {
    const element = await render(GENRES, true);
    expect(emissionFrom(element, 1, 'ArrowRight', 'none')).toBeNull();
  });

  it('does not reorder a row that is not orderable (the tags row)', async () => {
    const element = await render(GENRES, false);
    expect(emissionFrom(element, 1, 'ArrowRight', 'ctrl')).toBeNull();
  });

  describe('startExpanded', () => {
    it('starts in read-only mode by default, so an empty row is not just a bare edit icon', async () => {
      const element = await render([], false);
      expect(element.querySelector('.editable-chips__field')).toBeNull();
    });

    it('starts already in edit mode when startExpanded is set — a create form has nothing to show read-only', async () => {
      const element = await render([], false, true);
      expect(element.querySelector('.editable-chips__field')).not.toBeNull();
      expect(element.querySelector('mat-label')?.textContent).toBe('Genres');
    });
  });
});
