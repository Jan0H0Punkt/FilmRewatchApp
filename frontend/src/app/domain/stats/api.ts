/** Stats data access (DESIGN §6.1) — the only place that speaks the wire shape. */
import { HttpClient, httpResource } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';

interface TopNameDto {
  readonly name: string;
  readonly watches: number;
  readonly average_rating: number;
  readonly score: number;
}

/** Mirrors the backend's `StatsBlockRead`. */
export interface StatsBlockDto {
  readonly watches: number;
  readonly first_watches: number;
  readonly rewatches: number;
  readonly films_released_that_year: number | null;
  readonly distinct_films: number;
  readonly minutes_watched: number;
  readonly average_rating: number | null;
  readonly rating_distribution: readonly { readonly value: number; readonly count: number }[];
  readonly top_genres: readonly TopNameDto[];
  readonly top_directors: readonly TopNameDto[];
  readonly top_tags: readonly TopNameDto[];
  readonly top_films: readonly {
    readonly film_id: string;
    readonly title: string;
    readonly watches: number;
    readonly average_rating: number;
    readonly score: number;
  }[];
  /** `"1"`…`"12"` in a year block, `"2025"` in the all-time block. */
  readonly buckets: readonly { readonly label: string; readonly count: number }[];
}

/** Mirrors the backend's `StatsRead`. */
export interface StatsDto {
  readonly total: StatsBlockDto;
  readonly years: readonly (StatsBlockDto & { readonly year: number })[];
}

@Injectable({ providedIn: 'root' })
export class StatsApi {
  private readonly http = inject(HttpClient);

  /** `GET /stats` — an `httpResource` for its loading/error signals, as `RewatchApi.list`. */
  readonly stats = httpResource<StatsDto>(() => `${environment.apiBaseUrl}/stats`);

  /** One-shot `GET /stats`, for a caller that must await the fresh numbers (`StatsFacade.refresh`). */
  fetch(): Observable<StatsDto> {
    return this.http.get<StatsDto>(`${environment.apiBaseUrl}/stats`);
  }
}
