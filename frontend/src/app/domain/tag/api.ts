/**
 * Tag data access (DESIGN §6.1) — the only place that speaks the wire shape.
 *
 * Read-only: tags are never created or deleted directly. They come into
 * existence through a film payload's `tags` list and die with their last film
 * link (FR-TAG-01/04), so the backend exposes no write route here.
 *
 * Views never inject this — they go through `TagFacade`.
 */
import { httpResource } from '@angular/common/http';
import { Injectable } from '@angular/core';

import { environment } from '../../../environments/environment';

/** One tag row from `GET /tags` (mirrors `TagRead`). */
export interface TagDto {
  readonly id: string;
  readonly name: string;
  readonly created_at: string;
}

@Injectable({ providedIn: 'root' })
export class TagApi {
  /**
   * `GET /tags` — every tag, alphabetically, fetched once.
   *
   * The route also takes a `?prefix=` filter (FR-TAG-06), which this
   * deliberately does not use: a personal library holds a few dozen tags, so
   * one request plus client-side filtering beats a round trip per keystroke.
   */
  readonly list = httpResource<readonly TagDto[]>(() => `${environment.apiBaseUrl}/tags`, {
    defaultValue: [],
  });
}
