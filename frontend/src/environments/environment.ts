/**
 * Frontend → backend wiring (DESIGN §8) — the single wiring point, M0 PR7.
 *
 * The API base URL is hard-coded into the Angular build: the laptop's **LAN
 * address** (not `localhost`) so the mobile PWA on the same Wi‑Fi can reach
 * the backend (§8.2). Repointing at a different backend — a new laptop, a
 * different network — means editing this value and rebuilding the frontend
 * (§8); the backend must then be served on that interface (`--host 0.0.0.0`),
 * not only on loopback. The backend's `CORS_ALLOWED_ORIGINS` must
 * include this app's origin (see docker-compose.yml).
 */
export const environment = {
  /** Versioned API root (§3.2) that every data-access call builds on. */
  apiBaseUrl: 'http://localhost:8000/api/v1',
} as const;
