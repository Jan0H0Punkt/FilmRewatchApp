# Future Work & Deferred Items ("Maybe Later")

**Version:** 1.0  
**Status:** Living  
**Created:** 2026-06-05  
**Last updated:** 2026-07-12  
**Companion to:** [REQUIREMENTS_V1.md](./REQUIREMENTS_V1.md) · [DESIGN_V1.md](../designs/DESIGN_V1.md) · [OPEN_DECISIONS_V1.md](./OPEN_DECISIONS_V1.md)  

Work intentionally **out of scope for this version** but worth doing later. Nothing here is required for the
first release; each item notes why it was deferred and where it would slot in. This is a living backlog.

---

## Global tag/genre delete (FR-TAG-05)

Deleting a tag (or genre) from the **entire library** in one action — distinct from removing a label from a single
film, which is covered by per-film edit + orphan cleanup (FR-TAG-04, still in scope).

- **Why deferred:** it needs a management/settings screen, which the three-view plan (§7) doesn't provide. There
  is no natural home for the "delete this everywhere — affects N films" confirmation flow.
- **Future shape:** a "settings" screen with matching `DELETE /tags/{id}` and `DELETE /genres/{id}` endpoints
  (the global delete returns the affected-film count for confirmation, per FR-TAG-05).
- **Design refs:** DESIGN §5.3 (API surface note), §6.5.

## Rewatch list filtering

Filter the Rewatch due-list by film attributes (tag, genre, director, …).

- **Why deferred:** not needed for the first release; the Rewatch view ships render-only.
- **Key property:** filtering is a **subset** operation that preserves the algorithm's order — it only *removes*
  non-matching films, never re-sorts, so it does **not** conflict with FR-RW-04.
- **Future shape:** runs client-side over the already-cached due-list (join each `film_id` to cached metadata) and
  **reuses the Search & Filter registry** (FR-EXT-05) rather than building a second filtering mechanism. Works
  offline since the due-list is cached.
- **Design refs:** DESIGN §6.3.

## CI/CD automation

No automation for now — there is no CI provider in use, so tests (DESIGN §9) and the strict type checks
(DESIGN §5.7) are run **by hand** locally (editor feedback + a `make`/script target).

- **Why deferred:** no provider; not blocking for a solo, laptop-only project.
- **Future options (no design impact):**
  - **Local pipeline** — `pre-commit` hooks running a `make`/`just` task runner (lint + typecheck + tests on
    commit), optionally **`act`** to run GitHub-Actions workflows locally in Docker.
  - **Hosted provider** — a normal CI service later, if/when one is available.
  - **Local CD** — a `make up` / git hook that rebuilds and restarts the Docker Compose stack.
- **Design refs:** DESIGN §5.7, §8.1.

## Same-origin reverse proxy (frontend ↔ backend wiring)

v1 hard-codes the API base URL in the Angular build (DESIGN §8). A later release could instead serve the frontend
and backend on the **same origin** behind a reverse proxy (nginx or Caddy serving the built app + proxying
`/api/*` to FastAPI), so the frontend calls the relative `/api/v1`.

- **Why deferred:** the hard-coded URL is enough for the single laptop deployment; the proxy needs hands-on
  reverse-proxy familiarity first.
- **Benefit when adopted:** no hard-coded URL, no rebuild to repoint at a different backend, and CORS largely
  eliminated (same origin).
- **Design refs:** DESIGN §8.

## API access protection (unauthenticated LAN exposure)

The API is deliberately **unauthenticated** and reachable by every device on the home Wi‑Fi — §8.2 exposes port
8000 so the phone can reach it, and CORS constrains *browsers* only, not direct HTTP clients (`curl`, scripts).
For v1 this is an **accepted risk** (recorded 2026-07-12, REVIEW_M0 §2.1): single user, trusted home LAN, and
authentication is explicitly out of scope per REQUIREMENTS §1.3.

- **Why deferred:** single-user app on a trusted home network; no auth in scope (REQUIREMENTS §1.3). "For now
  it's fine" — but a different solution should be found eventually rather than leaving this permanent.
- **Future shape (options, cheapest first):** a static bearer token the client sends in a header, checked by one
  FastAPI middleware; or authentication enforced at the same-origin reverse proxy (see the entry above — adopting
  the proxy would provide the enforcement point nearly for free). Revisit immediately if the network stops being
  trusted or the user model changes.
- **Design refs:** DESIGN §3.6 (CORS), §8.2 (deployment/exposure); REVIEW_M0 §2.1.

## External metadata integration (adapter pattern)

Integrating an external film-metadata source (e.g. TMDB) as an **optional lookup step** during film creation that
pre-fills the form, via a dedicated adapter module — without touching the manual-entry or persistence flow.

- **Why deferred:** the first release plans no external integration; this gets tackled when an actual integration
  is wanted.
- **Future shape:** a dedicated `adapters/` module that translates external API responses into the internal data
  model (additive — core create/edit never imports an adapter), toggled by a feature flag; a designated "search
  external source" action in the Add Film flow pre-fills the form, leaving submit/persist unchanged.
- **Requirement refs:** REQ §3.4, FR-EXT-06/07/08 (the requirements' extensibility intent for this seam).
