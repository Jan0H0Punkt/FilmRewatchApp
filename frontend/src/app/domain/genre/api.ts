/**
 * Genre data access (DESIGN §6.1) — the only place that speaks the wire shape.
 *
 * Read-only, exactly like `tag/api.ts`: genres are modelled as tags are
 * (REQ §4.4), created through a film payload's `genre` list and deleted with
 * their last film link, so there is no write route here.
 *
 * Views never inject this — they go through `GenreFacade`.
 */
import { httpResource } from '@angular/common/http';
import { Injectable } from '@angular/core';

import { environment } from '../../../environments/environment';

/** One genre row from `GET /genres` (mirrors `GenreRead`). */
export interface GenreDto {
  readonly id: string;
  readonly name: string;
  readonly created_at: string;
}

@Injectable({ providedIn: 'root' })
export class GenreApi {
  /**
   * `GET /genres` — every genre, alphabetically, fetched once. The route's
   * `?prefix=` filter goes unused for the same reason as `GET /tags`: the
   * list is small enough to filter client-side.
   */
  readonly list = httpResource<readonly GenreDto[]>(() => `${environment.apiBaseUrl}/genres`, {
    defaultValue: [],
  });
}
