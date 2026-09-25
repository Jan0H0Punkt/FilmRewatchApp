/**
 * Settings data access (DESIGN §6.1) — the only place that speaks the wire shape.
 *
 * A one-row singleton (`backend/app/settings/`, FR-RW-08): `GET`/`PUT
 * /settings` both take and return the same shape, no id in the URL.
 */
import { HttpClient, httpResource } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';

/** Mirrors the backend's settings read/write shape. */
export interface SettingsDto {
  readonly rewatch_share: number | null;
}

@Injectable({ providedIn: 'root' })
export class SettingsApi {
  private readonly http = inject(HttpClient);

  /** `GET /settings` — the stored row. */
  readonly settings = httpResource<SettingsDto>(() => `${environment.apiBaseUrl}/settings`);

  /** `PUT /settings` — replaces the stored row and returns it back. */
  save(dto: SettingsDto): Observable<SettingsDto> {
    return this.http.put<SettingsDto>(`${environment.apiBaseUrl}/settings`, dto);
  }
}
