/**
 * Rating data access (DESIGN §6.1) — the only place that speaks the wire shape.
 *
 * Plain `HttpClient` calls, not `httpResource`: both routes here are writes,
 * and `httpResource` is reads-only. Views never inject this — they go
 * through `RatingFacade`.
 */
import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import type { RatingEntryDto } from '../film/api';

/**
 * The `POST /films/{id}/ratings` payload (mirrors `RatingCreate`). `value`
 * is required but nullable — an explicit `null` states "watched, not rated"
 * (FR-RAT-12); the key is never omitted.
 */
export interface RatingCreateDto {
  readonly value: number | null;
  readonly watch_date: string;
}

/** The `DELETE /ratings/{id}` outcome (mirrors `RatingDeletionResult`). */
export interface RatingDeletionResultDto {
  readonly rating_id: string;
  readonly film_id: string;
  readonly film_deleted: boolean;
}

@Injectable({ providedIn: 'root' })
export class RatingApi {
  private readonly http = inject(HttpClient);

  /** `POST /films/{id}/ratings` — records a new rating event (FR-RAT-01..04). */
  add(filmId: string, dto: RatingCreateDto): Observable<RatingEntryDto> {
    return this.http.post<RatingEntryDto>(`${environment.apiBaseUrl}/films/${filmId}/ratings`, dto);
  }

  /** `DELETE /ratings/{id}` — FR-RAT-07; may cascade into deleting the film. */
  remove(ratingId: string): Observable<RatingDeletionResultDto> {
    return this.http.delete<RatingDeletionResultDto>(`${environment.apiBaseUrl}/ratings/${ratingId}`);
  }
}
