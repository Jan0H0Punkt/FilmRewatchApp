/**
 * A chip row that can be edited in place — read-only chips plus an edit
 * button that swaps in Material's chip grid with an autocomplete input.
 *
 * Dumb by design (§6.1): it owns no data and performs no write. Each change
 * emits the **complete** new list through `changed`; the parent decides what
 * that means and persists it. Used for a film's tags and its genres, which
 * are the same shape on the wire (a full replacement list of names) and the
 * same shape on screen.
 */
import { ChangeDetectionStrategy, Component, computed, input, linkedSignal, output, signal } from '@angular/core';
import { CdkDrag, CdkDropList, moveItemInArray, type CdkDragDrop } from '@angular/cdk/drag-drop';
import { COMMA, ENTER } from '@angular/cdk/keycodes';
import { MatAutocompleteModule, type MatAutocompleteSelectedEvent } from '@angular/material/autocomplete';
import { MatButtonModule } from '@angular/material/button';
import { MatChipsModule, type MatChipInputEvent } from '@angular/material/chips';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';

@Component({
  selector: 'app-editable-chips',
  imports: [
    CdkDrag,
    CdkDropList,
    MatAutocompleteModule,
    MatButtonModule,
    MatChipsModule,
    MatFormFieldModule,
    MatIconModule,
  ],
  templateUrl: './editable-chips.html',
  styleUrl: './editable-chips.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class EditableChips {
  /** The row's name, shown as the form field's label — e.g. `Tags`. */
  readonly label = input.required<string>();
  /** The singular noun for per-chip labels — e.g. `tag`, giving "Remove tag heist". */
  readonly itemNoun = input.required<string>();
  readonly values = input.required<readonly string[]>();
  /** The full vocabulary to autocomplete against; already-assigned values are filtered out below. */
  readonly suggestions = input.required<readonly string[]>();
  /**
   * Lets chips be dragged (or Ctrl/Cmd+Arrow'd) into a deliberate order —
   * genres only; tags keep arriving in whatever order the server returns.
   * Defaults to `false` so the tags row is unaffected.
   */
  readonly orderable = input(false);
  /**
   * Opens the row already in edit mode instead of the read-only chip set —
   * for a row that starts empty (a create form's genres/tags), the read-only
   * mode has nothing to show but a bare, unlabelled edit icon.
   */
  readonly startExpanded = input(false);
  /** The complete list after an add, a remove, or a reorder — never a delta. */
  readonly changed = output<readonly string[]>();

  /**
   * Edit mode, seeded from `startExpanded` — a `linkedSignal`, not a plain
   * `signal`, because a bound input isn't resolved yet when a field
   * initializer runs; `toggleEditing` below still just flips it freely
   * after that. There is no draft state behind it: the parent saves each
   * emitted list immediately, so leaving edit mode discards nothing.
   */
  protected readonly isEditing = linkedSignal(() => this.startExpanded());
  /** What has been typed into the input, narrowing `options` below. */
  protected readonly query = signal('');
  /** Enter and comma both commit the typed text as a chip. */
  protected readonly separators = [ENTER, COMMA];

  /**
   * Suggestions not already on the row, prefix-matched against the typed
   * text — mirroring the `?prefix=` semantics the backend lookups offer for
   * the same job (FR-TAG-06 and its genre analogue).
   */
  protected readonly options = computed<readonly string[]>(() => {
    const query = this.query().trim().toLowerCase();
    const assigned = new Set(this.values().map((value) => value.toLowerCase()));
    return this.suggestions().filter(
      (name) => !assigned.has(name.toLowerCase()) && name.toLowerCase().startsWith(query),
    );
  });

  protected toggleEditing(): void {
    this.isEditing.update((editing) => !editing);
    this.query.set('');
  }

  /** A name typed and committed with Enter or comma — may not exist server-side yet (FR-TAG-01). */
  protected addTyped(event: MatChipInputEvent): void {
    this.add(event.value);
    event.chipInput.clear();
    this.query.set('');
  }

  /** A name picked from the autocomplete panel. */
  protected addSuggested(event: MatAutocompleteSelectedEvent, input: HTMLInputElement): void {
    this.add(String(event.option.value));
    input.value = '';
    this.query.set('');
  }

  private add(name: string): void {
    const trimmed = name.trim();
    if (trimmed === '') return;
    // The backend dedupes labels case-insensitively (FR-TAG-02) and would
    // collapse the duplicate silently; not emitting it keeps the row honest.
    if (this.values().some((value) => value.toLowerCase() === trimmed.toLowerCase())) return;
    this.changed.emit([...this.values(), trimmed]);
  }

  /**
   * Removes one chip. The last one cannot go: both lists this row serves are
   * `min_length=1` on the wire, so the API would reject an empty list (the
   * template hides the control too, this is the guard behind it).
   */
  protected remove(name: string): void {
    if (this.values().length <= 1) return;
    this.changed.emit(this.values().filter((value) => value !== name));
  }

  /** A drag released over a new slot. */
  protected onDrop(event: CdkDragDrop<unknown>): void {
    if (event.previousIndex === event.currentIndex) return;
    this.reorder(event.previousIndex, event.currentIndex);
  }

  /**
   * The keyboard path for reordering — dragging alone would leave it
   * unreachable without a pointer (NFR-A11Y-02). Mirrors Material's own
   * chip-grid navigation, which already ignores modified arrow keys, so
   * Ctrl/Cmd+Arrow never fights the grid's plain-arrow focus movement.
   */
  protected onChipKeydown(event: KeyboardEvent, index: number): void {
    if (!this.orderable() || !(event.ctrlKey || event.metaKey)) return;
    const step = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0;
    if (step === 0) return;
    const target = index + step;
    if (target < 0 || target >= this.values().length) return;
    event.preventDefault();
    this.reorder(index, target);
  }

  private reorder(previousIndex: number, currentIndex: number): void {
    const next = [...this.values()];
    moveItemInArray(next, previousIndex, currentIndex);
    this.changed.emit(next);
  }
}
