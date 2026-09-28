/** Letterboxd data access (DESIGN §6.1) — the only place that speaks the `/letterboxd` wire shape. */
import { HttpClient, httpResource } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';

const BASE = `${environment.apiBaseUrl}/letterboxd`;

export interface LetterboxdEntryDto {
  readonly id: string;
  readonly film_title: string;
  readonly film_year: number;
  readonly film_url: string;
  readonly watched_date: string;
  readonly rating: number | null;
  readonly rewatch: boolean;
  readonly suggested_film: { readonly id: string; readonly title: string } | null;
}

@Injectable({ providedIn: 'root' })
export class LetterboxdApi {
  private readonly http = inject(HttpClient);

  /** `GET /letterboxd/entries` — the open review list. */
  readonly entries = httpResource<LetterboxdEntryDto[]>(() => `${BASE}/entries`);

  /** `POST …/assign` — approve the suggestion or assign another film (FR-LBX-06). */
  assign(entryId: string, filmId: string): Observable<unknown> {
    return this.http.post(`${BASE}/entries/${entryId}/assign`, { film_id: filmId });
  }

  /** `POST …/dismiss`. */
  dismiss(entryId: string): Observable<unknown> {
    return this.http.post(`${BASE}/entries/${entryId}/dismiss`, null);
  }

  /** `POST /letterboxd/sync` — read the feed now. */
  sync(): Observable<unknown> {
    return this.http.post(`${BASE}/sync`, null);
  }
}
