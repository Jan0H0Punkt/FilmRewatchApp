/**
 * Film data access (DESIGN §6.1) — the only place that speaks the wire shape.
 *
 * Snake_case DTOs stay inside this file and `mapper.ts`; everything above the
 * data layer sees the camelCase domain model. Views never inject this — they
 * go through `FilmFacade`.
 */
import { HttpClient, httpResource } from '@angular/common/http';
import { Injectable, effect, inject, signal } from '@angular/core';
import type { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';

/**
 * One title in the §7.3 projection (mirrors `TitleRead` — includes `is_original`).
 * Part of the complete film projection returned by both `GET /films` and `GET /films/{id}`.
 */
export interface TitleDto {
  readonly value: string;
  readonly is_primary: boolean;
  readonly is_original: boolean;
}

/** One rating event embedded in the projection (mirrors `RatingEntryRead`). */
export interface RatingEntryDto {
  readonly id: string;
  /** `null` for a watch the user chose not to rate (FR-RAT-12). */
  readonly value: number | null;
  readonly watch_date: string;
  readonly created_at: string;
}

/**
 * The §7.3 film projection returned by both `GET /films` and `GET /films/{id}`
 * (mirrors `FilmDetailRead`). The library list view deliberately maps only a subset
 * of these fields via `toFilm`; the detail view renders the full projection via
 * `toFilmDetail`.
 */
export interface FilmDto {
  readonly id: string;
  readonly titles: readonly TitleDto[];
  readonly release_year: number;
  readonly director: string;
  readonly runtime_minutes: number;
  readonly genre: readonly string[];
  readonly tags: readonly string[];
  readonly poster_image: string | null;
  readonly letterboxd_url: string | null;
  readonly is_favorite: boolean;
  readonly delay_days: number;
  readonly rating_history: readonly RatingEntryDto[];
  readonly created_at: string;
  readonly updated_at: string;
}

/**
 * The `PATCH /films/{id}` payload (mirrors `FilmUpdate`) — every field
 * optional, absent means unchanged (FR-LIB-06/07). The detail view sets
 * `is_favorite`, `delay_days`, or `tags`; the remaining editable fields join
 * here when the edit form needs them.
 */
export interface FilmUpdateDto {
  readonly is_favorite?: boolean;
  readonly delay_days?: number;
  /** The full replacement tag list (FR-TAG-03), never a delta. */
  readonly tags?: readonly string[];
  /** The full replacement genre list. Singular on the wire, unlike `tags`. */
  readonly genre?: readonly string[];
  /** Absent means unchanged; an explicit `null` clears the link (FR-LIB-15). */
  readonly letterboxd_url?: string | null;
}

/** One title in the `POST /films` payload (mirrors `TitleCreate`). Unflagged means "the lone title, primary by default". */
export interface TitleCreateDto {
  readonly value: string;
  readonly is_primary?: boolean;
  readonly is_original?: boolean;
}

/** The `POST /films` payload (mirrors `FilmCreate`) — a film plus its mandatory first rating (FR-LIB-01..03). */
export interface FilmCreateDto {
  readonly titles: readonly TitleCreateDto[];
  readonly release_year: number;
  readonly director: string;
  readonly runtime_minutes: number;
  readonly genre: readonly string[];
  readonly tags: readonly string[];
  readonly poster_image: string | null;
  readonly first_rating: {
    readonly value: number | null;
    readonly watch_date: string;
  };
}

@Injectable({ providedIn: 'root' })
export class FilmApi {
  private readonly http = inject(HttpClient);

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

  /**
   * The film currently shown by the detail view; `null` before one is
   * selected. `GET /films` already returns the same §7.3 projection
   * `GET /films/{id}` would, so selecting an id already present in `list`
   * makes no request at all — `detail` below only fires for the rare miss.
   */
  readonly selectedId = signal<string | null>(null);

  /**
   * `GET /films/{id}` — a fallback for a `selectedId` that `list` doesn't
   * (yet) hold: a stale bookmark, a hand-typed id, or a film deleted by
   * someone else. The URL factory returns `undefined` — `httpResource`'s
   * documented way to skip the request — whenever the id is already in
   * `list`, which is the common case.
   *
   * `FilmFacade` only reads `isLoading`/`error` off this resource, never
   * `value`: the constructor below folds a resolved fetch into `list`, so
   * `list` stays the single source of truth `FilmFacade.detail` looks up
   * (a genuine miss surfaces as this request's 404, which `FilmFacade`
   * maps to its not-found state).
   */
  readonly detail = httpResource<FilmDto>(() => {
    const id = this.selectedId();
    if (id === null) return undefined;
    // Whether this is a miss is only knowable once `list` has landed, and
    // asking early does more than guess wrong: the fold-in below writes to
    // `list.value`, and a resource write aborts that resource's in-flight
    // request. Racing the library load would therefore cancel it and strand
    // `list` holding just this one film.
    if (this.list.isLoading()) return undefined;
    // A failed `list` can't answer "is it already in the list" either:
    // Angular 22's `httpResource.value()` THROWS `ResourceValueError` once
    // its resource has errored, rather than falling back to `defaultValue`.
    // This factory runs inside `list`'s own effect, so an unguarded read
    // here crashes on the next tick after ANY `/films` reload fails while a
    // film is selected — `selectedId` is never cleared on leaving the detail
    // view, so that includes reloads long after this resource last fired.
    // Bail out like the race guard above; a later successful reload clears
    // `list.error()` and re-runs this normally.
    if (this.list.error()) return undefined;
    const inList = this.list.value().some((film) => film.id === id);
    return inList ? undefined : `${environment.apiBaseUrl}/films/${id}`;
  });

  constructor() {
    effect(() => {
      const dto = this.detail.value();
      if (dto === undefined) return;
      this.list.value.update((films) => (films.some((film) => film.id === dto.id) ? films : [...films, dto]));
    });
  }

  /**
   * `PATCH /films/{id}` — a plain `HttpClient` call, not `httpResource`
   * (writes only). Returns the full §7.3 projection, same shape as `GET`.
   */
  update(id: string, dto: FilmUpdateDto): Observable<FilmDto> {
    return this.http.patch<FilmDto>(`${environment.apiBaseUrl}/films/${id}`, dto);
  }

  /** `POST /films` (FR-LIB-01..03) — 201 with the full §7.3 projection, same shape as `GET`. */
  create(dto: FilmCreateDto): Observable<FilmDto> {
    return this.http.post<FilmDto>(`${environment.apiBaseUrl}/films`, dto);
  }

  /** `DELETE /films/{id}` (FR-LIB-10..12) — 204 No Content on success. */
  remove(id: string): Observable<void> {
    return this.http.delete<void>(`${environment.apiBaseUrl}/films/${id}`);
  }
}
