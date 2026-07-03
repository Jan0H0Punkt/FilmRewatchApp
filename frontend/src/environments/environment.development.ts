/**
 * Development override of the §8 wiring (swapped in by `ng serve` via the
 * `fileReplacements` in angular.json). Points at the Compose-published
 * backend on the same machine (docker-compose.yml maps 8000:8000); the
 * backend's default `CORS_ALLOWED_ORIGINS` already allows the dev origin
 * `http://localhost:4200`.
 */
export const environment = {
  /** Versioned API root (§3.2) that every data-access call builds on. */
  apiBaseUrl: 'http://localhost:8000/api/v1',
} as const;
