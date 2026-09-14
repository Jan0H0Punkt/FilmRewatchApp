/**
 * Rewatch data access (DESIGN §6.1, §6.3) — the only place that speaks the wire shape.
 *
 * Read-only: the due-list is computed and stored by the backend's daily job
 * (§5.8), so there is no write here. The client's one local change to it —
 * removing a film the user just watched — is `RewatchFacade.removeFilm`,
 * which edits the cached value rather than calling the API.
 */
import { httpResource } from '@angular/common/http';
import { Injectable } from '@angular/core';

import { environment } from '../../../environments/environment';

/** One entry of the daily due-list (mirrors `RewatchSuggestionRead`). */
export interface RewatchSuggestionDto {
  readonly film_id: string;
  /** Always `<= 0`: `0` is due today, negative is overdue by that many days. */
  readonly days_until_next_rewatch: number;
}

@Injectable({ providedIn: 'root' })
export class RewatchApi {
  /**
   * `GET /rewatch-suggestions` — the stored result of the last daily run.
   *
   * An `httpResource` for the same reason `FilmApi.list` is one: it exposes
   * loading and error as signals, which is the loading/empty/error triple
   * §7.1 has to render. Its `value` is writable, which is what makes the
   * §6.3 optimistic removal a local update rather than a refetch.
   */
  readonly list = httpResource<readonly RewatchSuggestionDto[]>(() => `${environment.apiBaseUrl}/rewatch-suggestions`, {
    defaultValue: [],
  });
}
