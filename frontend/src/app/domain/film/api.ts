/**
 * Film data access (DESIGN §6.1) — the only place that speaks the wire shape.
 *
 * Snake_case DTOs stay inside this file and `mapper.ts`; everything above the
 * data layer sees the camelCase domain model. Views never inject this — they
 * go through `FilmFacade`.
 */
import { httpResource } from '@angular/common/http';
import { Injectable } from '@angular/core';

import { environment } from '../../../environments/environment';

/** One title in the wire projection (REQ §4.1 Title object). */
export interface TitleDto {
  readonly value: string;
  readonly is_primary: boolean;
}

/** The §7.3 film projection, as `GET /films` and `GET /films/{id}` return it. */
export interface FilmDto {
  readonly id: string;
  readonly titles: readonly TitleDto[];
  readonly release_year: number;
  readonly director: string;
  readonly genre: readonly string[];
  readonly tags: readonly string[];
  readonly poster_image: string | null;
  readonly average_rating: number;
  readonly is_favorite: boolean;
}

@Injectable({ providedIn: 'root' })
export class FilmApi {
  /**
   * `GET /films` — the whole library, primary-title ordered (§5.3).
   *
   * An `httpResource` rather than a bare `HttpClient` call: it exposes the
   * request's loading and error state as signals, which is exactly the
   * loading/empty/error triple the views have to render (REQ §7.2).
   */
  readonly list = httpResource<readonly FilmDto[]>(() => `${environment.apiBaseUrl}/films`, {
    defaultValue: [],
  });
}
