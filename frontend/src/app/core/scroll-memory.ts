/**
 * Remembers each view's last scroll offset for the current app session, so
 * navigating away and back restores where the user left off. In-memory only
 * (a plain `Map` on a root-provided singleton) — a reload or fresh app start
 * clears it naturally, without needing to distinguish that from any other reset.
 */
import { Injectable } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class ScrollMemoryService {
  private readonly positions = new Map<string, number>();

  save(key: string, y: number): void {
    this.positions.set(key, y);
  }

  restore(key: string): number {
    return this.positions.get(key) ?? 0;
  }
}
