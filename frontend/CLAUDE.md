# CLAUDE.md — Frontend (Angular)

Guidance for the Angular client under `frontend/`. See the repo-root `CLAUDE.md` for cross-cutting orientation, the design-doc-driven / milestone-sequenced workflow, and the `docs/` map.

**The repo is in M0 ("Scaffolding").** The workspace is a **buildable, empty shell** (M0 PR7): the §4 folder skeleton exists as README placeholders, the route registry is empty, and the root component is a placeholder. Real views, the adaptive navigation (drawer/bottom bar), shared components, and the data/cache layer all arrive in **M3+**. Do not add them to a milestone that doesn't own them (see the out-of-scope table in `docs/milestones/MILESTONE_M0_V1.md`).

## Commands

All frontend commands run from `frontend/`. Requires Node.js ≥ 20 (workspace generated with Node 24 / Angular 22).

```bash
npm install          # one-time setup
npm run build        # ng build — production by default; strict type-check included, must be clean
npm start            # ng serve — dev server at http://localhost:4200 (uses environment.development.ts)
npm test             # ng test — vitest unit tests
npm run lint         # ng lint — ESLint (angular-eslint flat config in eslint.config.js)
npm run format       # prettier --write (config: .prettierrc, ignores: .prettierignore)
npm run format:check # prettier --check — what the pre-commit hook runs on staged files
```

There is no CI — a clean `ng build` (which runs the strict TS + template type-check), `ng test`, and `npm run lint` are the local gate for every change. Treat a type error as a build break (DESIGN §5.7). The ESLint template config includes `templateAccessibility` — a11y findings in templates are lint errors (NFR-A11Y-01..04).

A repo-level pre-commit hook (`.githooks/pre-commit`, enabled once per clone with `git config core.hooksPath .githooks`) Prettier-checks staged frontend files and runs `ng lint` before every commit that touches `frontend/`.

## Architecture

### Layering (§6.1)

Calls flow **downward only** — views → domain facades → data access; data returns upward:

- `src/app/views/*` — presentation: the three screens (`rewatch/`, `library/`, `film-detail/`). Call business-logic facades **only**, never the data layer; hold no rules.
- `src/app/domain/<entity>/` — business logic + data access **per entity** (`film/`, `rating/`, `tag/`, `genre/`), mirroring the backend's feature modules: `model.ts`, `validators.ts`, `mapper.ts`, `api.ts` (data access), `facade.ts` (the single API views call).
- `src/app/shared/` — reusable dumb UI components + display pipes (FR-EXT-03), WCAG 2.1 AA.
- `src/app/core/` — cross-cutting infra: HTTP client, cache-first + sync engine (§3.7/§6.2, M3+), config, errors, and the **route registry**.

**Three models, two mappings** (§6.1): DTO (wire shape, data access) → domain model (canonical, shared per entity) → ViewModel (display-ready, per view). Read: `DTO → Domain → ViewModel`; write: `form input → validate → Domain → DTO`.

### Routing (§6.5)

Routes are driven by the **route registry** (`src/app/core/route-registry.ts`): a new view is added by appending a `RouteRegistryEntry` — never by editing `app.routes.ts`, which only projects the registry into Angular `Routes` (FR-EXT-02).

### Configuration (§8)

`src/environments/environment.ts` is the **single wiring point** to the backend: `apiBaseUrl` is hard-coded into the build — the laptop's **LAN address** (placeholder until known) so the mobile PWA can reach it. `ng serve` swaps in `environment.development.ts` (localhost) via `fileReplacements`. Repointing the production build means rebuilding. The backend's `CORS_ALLOWED_ORIGINS` must include this app's origin (see `docker-compose.yml`).

## Conventions

- **Strict type-safety everywhere** (§5.7): the `tsconfig.json` strict family plus `strictTemplates` are on — set explicitly in M0 PR7 (Angular 22's `ng new` no longer emits `"strict": true`; do not remove it). No `any` leakage.
- **Standalone components** (no NgModules); Angular Material for UI components (§2).
- Cite design sections and requirement IDs (`§6.5`, `FR-EXT-02`) as pointers in comments, not paraphrases. Comment length and placement follow the `code-docs` skill.
