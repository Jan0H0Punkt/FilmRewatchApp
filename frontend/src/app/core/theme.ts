/**
 * Colour-scheme preference — light, dark, or the system setting (`auto`).
 *
 * The preference is written to `<html data-theme>`, which `styles.scss` turns
 * into a `color-scheme`; Angular Material's M3 system variables follow that
 * automatically, so no component needs a theme-aware branch of its own.
 */
import { Injectable, effect, signal } from '@angular/core';

export type ThemePreference = 'light' | 'dark' | 'auto';

const STORAGE_KEY = 'theme-preference';
const PREFERENCES: readonly ThemePreference[] = ['light', 'dark', 'auto'];

function isPreference(value: string | null): value is ThemePreference {
  return value !== null && (PREFERENCES as readonly string[]).includes(value);
}

/** Private browsing and blocked site data make `localStorage` throw on access. */
function storedPreference(): ThemePreference {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return isPreference(stored) ? stored : 'auto';
  } catch {
    return 'auto';
  }
}

@Injectable({ providedIn: 'root' })
export class ThemeService {
  readonly preference = signal<ThemePreference>(storedPreference());

  /** Advances to the next preference in `PREFERENCES` order, wrapping after `auto`. */
  cycle(): void {
    const next = PREFERENCES[(PREFERENCES.indexOf(this.preference()) + 1) % PREFERENCES.length];
    this.preference.set(next);
  }

  constructor() {
    effect(() => {
      const preference = this.preference();
      document.documentElement.dataset['theme'] = preference;
      try {
        localStorage.setItem(STORAGE_KEY, preference);
      } catch {
        // A preference that cannot be persisted still applies for this visit.
      }
    });
  }
}
