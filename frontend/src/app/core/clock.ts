/**
 * A shared "now", ticking once a minute, for any view that displays a
 * live-ish time (e.g. "done by" estimates). One root-provided timer for the
 * whole app instead of a `setInterval` per component.
 */
import { Injectable, signal } from '@angular/core';

const TICK_MS = 60_000;

@Injectable({ providedIn: 'root' })
export class ClockService {
  readonly now = signal(Date.now());

  constructor() {
    setInterval(() => this.now.set(Date.now()), TICK_MS);
  }
}
