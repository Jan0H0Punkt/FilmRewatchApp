# REVIEW_M0 — Independent Review of the M0 Scaffolding

**Date:** 2026-07-03
**Scope:** Everything on `main` at the M0 exit point (commit `117773bb`) — backend, frontend, Docker stack, tooling, docs, git hygiene — checked for necessity, security, `.gitignore` coverage, tool choices, and current (mid-2026) best practices. Where this review disagrees with a decision recorded in `docs/`, it says so explicitly.
**Rule applied:** findings only; no code was changed.

---

## Executive summary

M0 is in very good shape: the layering discipline, strict typing on both tiers, config-over-code, the error envelope, and the Compose stack are all genuinely well executed, and the tool choices are almost all current best practice (verified against the July-2026 state of the ecosystem). The important findings are **not** in the code that was written — they are in what's *around* it:

| # | Finding | Severity |
|---|---------|----------|
| 1 | The **authoritative requirements doc was missing from `main`**; every other doc linked to it — ✅ **resolved 2026-07-03**: restored as `docs/requirements/REQUIREMENTS_V1.md` (typo fixed), all references updated | ~~High~~ resolved |
| 2 | `frontend/node_modules` (and `frontend/.angular` cache) were committed into `main`'s history — `.git` was ~98 MB — ✅ **resolved 2026-07-03**: history rewritten with `git filter-repo`, all branches force-pushed; `.git` now ~700 KB | ~~High~~ resolved |
| 3 | Postgres is published on `0.0.0.0:5432` with default credentials — reachable by anyone on the LAN — ✅ **resolved 2026-07-12**: loopback bind `127.0.0.1:5432:5432` | ~~High (security)~~ resolved |
| 4 | The API has no authentication and is deliberately LAN-exposed — nowhere recorded as an accepted risk — ✅ **addressed 2026-07-12**: recorded as accepted risk + future-work entry ("API access protection") with mitigation options | ~~Medium (security)~~ addressed |
| 5 | Backend has no dependency lockfile and no linter/formatter (frontend has both) — ✅ **resolved 2026-07-12**: uv adopted (committed `uv.lock`, `uv sync --frozen` Docker build) + Ruff lint/format wired into `make check` and the pre-commit hook | ~~Medium~~ resolved |
| 6 | Google Fonts loaded from CDN — contradicts the offline-first PWA goal | Medium |
| 7 | Root `.gitignore` gaps (`.DS_Store`, undocumented root `.env`, un-shareable `.claude/skills/`) — mostly addressed 2026-07-12: root `.DS_Store` ignore + root `.env.example` (README-documented) added; `.claude/skills/` sharing still open | Low (partial) |
| 8 | Assorted doc/code mismatches (missing `app/adapters/`, milestone doc still "Draft", stock frontend README) — `app/adapters/` ✅ resolved 2026-07-12 (decided: no folder, future-if-ever; docs annotated); milestone status + frontend README still open | Low (partial) |

Details, evidence, and recommendations below.

---

## 1. High-priority findings

### 1.1 The requirements document was missing from `main` — ✅ resolved

*(Resolved 2026-07-03, same day as the review.)* `CLAUDE.md`, `README.md`, `DESIGN_V1.md`, `FUTURE_WORK_V1.md`, and `MILESTONE_M0_V1.md` all linked to `docs/requirements/REQUIEREMENTS_V1.md`, but the file did not exist on `main` — it was lost when the docs were reorganised, surviving only on the unmerged branches `origin/plan/design_v1` and `origin/requierements_and_planing`. For a repo whose stated methodology is *design-doc-driven* with requirement IDs (`FR-LIB-04`, `NFR-MAINT-03`) cited throughout code and commits, the root of that traceability chain being absent was the single most important defect in M0.

**Resolution:** the file (v1.1, "Approved", 814 lines — verified content-identical to the `origin/plan/design_v1` copy) was restored as **`docs/requirements/REQUIREMENTS_V1.md`**, fixing the long-standing filename typo in the same move. All references across the five linking docs were updated, the in-file relative link to `DESIGN_V1.md` was corrected for the new location, and recovery artifacts (a stray diff hunk-header line, a missing trailing newline) were cleaned. Not yet committed at the time of writing.

### 1.2 `node_modules` was baked into git history — ✅ resolved

*(Resolved 2026-07-03, same day as the review.)* Commit `c58a3284` ("dummy frontend") and follow-ups (`7729caf2`, `1cedc009`) committed `frontend/node_modules` — and, as discovered during the fix, `frontend/.angular` build cache too — reachable from every branch. Result: `.git` weighed ~98 MB for a repo whose working tree is a few hundred KB, paid by every clone forever.

**Resolution:** history was rewritten with `git filter-repo --path frontend/node_modules --path frontend/.angular --invert-paths` and all five branches were force-pushed (`main` required temporarily allowing force-pushes in its branch protection rule — re-disable it). All 53 commits survive with identical tree content; `.git` shrank from ~98 MB to ~700 KB. A full pre-rewrite backup exists at `~/Projects/FilmRewatchApp-pre-rewrite-backup.bundle` (delete once confident). Residual caveats: any other clone of the repo must be **re-cloned, not pulled**, and GitHub may retain the old objects server-side via PR refs (e.g. PR #5) until its internal GC runs — fresh clones don't download those.

Still open from this finding: the stale branches (`plan/design_v1`, `requierements_and_planing`, `feat/m0`, `pr-4`) were rewritten and re-pushed rather than deleted; now that the requirements doc is recovered (1.1), they can be removed.

### 1.3 Postgres is exposed to the whole LAN with default credentials — ✅ resolved

*(Resolved 2026-07-12: the mapping is now `"127.0.0.1:5432:5432"`, with a comment explaining why the bind is loopback-only. The two smaller healthcheck notes below remain as accepted.)*

`docker-compose.yml` publishes `"5432:5432"`, which binds `0.0.0.0` — and the deployment target is a laptop that is *deliberately* on shared Wi‑Fi (that's how the phone reaches the backend). Combined with the default `filmrewatch`/`filmrewatch` credentials, **anyone on the same network can connect to the database with superuser rights on it**. The port is published only so host-side tooling (`psql`, Alembic) can reach the DB — that need is fully served by a loopback bind.

**Recommendation:** change the mapping to `"127.0.0.1:5432:5432"`. This is a one-line fix with zero workflow cost: the backend container reaches Postgres over the Compose network (unaffected), and host tools use localhost. The backend's `8000` port must stay LAN-exposed (the PWA needs it); Postgres must not.

Two smaller issues in the same file:
- The Postgres healthcheck hardcodes `pg_isready -U filmrewatch` — if `POSTGRES_USER` is ever overridden, the healthcheck lies. Use `${POSTGRES_USER:-filmrewatch}` (Compose interpolates healthcheck args).
- The backend healthcheck hardcodes port `8000`; overriding `PORT` would break it. Acceptable as-is, but worth a comment.

---

## 2. Security review (rest)

### 2.1 Unauthenticated, LAN-reachable write API — record the *exposure*, not just the scoping — ✅ addressed

*(Addressed 2026-07-12: recorded in `FUTURE_WORK_V1.md` as a new "API access protection" entry — the exposure is an explicitly accepted risk for now, with the mitigation options below (static bearer token / auth at the reverse proxy) listed as the future solution to pick from.)*

The recovered requirements doc (see 1.1) settles part of this: **"User authentication and multi-user support" is explicitly out of scope** (REQUIREMENTS §1.3), so no-auth is a recorded, deliberate decision — not an oversight, as an earlier draft of this finding suspected.

What remains open is narrower: scoping auth out is not the same as acknowledging that the *unauthenticated* API is deliberately reachable by every device on the Wi‑Fi (§8.2 exposes it for the phone). CORS is correctly configured, but **CORS only constrains browsers** — any LAN device can call `POST /api/v1/...` directly once M1 adds real endpoints. For a single-user home-network app this may be a perfectly fine accepted risk, but the *network* exposure (as opposed to the auth feature) is nowhere written down.

**Recommendation:** add one line to `OPEN_DECISIONS_V1.md` or the requirements' out-of-scope rationale (due M1, before real write endpoints exist): either explicitly accept "trusted home LAN, unauthenticated API", or plan the cheapest mitigation (a static bearer token checked by middleware, or auth at a reverse proxy — see 5.1, which would give this for free).

### 2.2 What's already done well

Worth stating, because it's a lot:
- **`.env` hygiene is correct**: both `.env` files are untracked (verified via `git check-ignore` and history — no env file or secret was ever committed), `.env.example` is committed and documents every variable, and `backend/.dockerignore` keeps `.env` out of the image build context.
- **Container runs as a non-root user** (`appuser`), no `.pyc` litter, `exec` hands PID 1 to uvicorn for clean signal handling.
- **CORS origins come from config** with `allow_credentials=False` — correct given no cookies/auth; wildcard methods/headers are fine in that combination.
- **The error envelope leaks nothing**: the catch-all 500 handler returns a fixed message, and there's a test asserting the exception text does not reach the client. Good.
- **Strict Pydantic at the boundary** (`strict=True`, `extra="forbid"`) is itself a security posture — it rejects smuggled/unknown fields by default.

### 2.3 Supply chain / reproducibility — ✅ resolved

*(Resolved 2026-07-12: uv adopted — `backend/uv.lock` committed (40 packages pinned), dev deps moved to uv's `[dependency-groups]`, the Dockerfile installs via a two-stage `uv sync --frozen --no-dev` with the uv image minor-pinned, and all commands/docs/Makefiles now go through `uv run`. Verified: pyright strict 0 errors, all tests green, `docker compose build backend` succeeds.)*

- The **backend has no lockfile**. `pyproject.toml` declares floors (`fastapi>=0.115`, etc.), so `pip install` — including *inside the Docker build* — resolves to whatever is newest at build time. Two builds a month apart produce different images; the "strict gate" certifies an environment that silently drifts. The frontend does this right (`package-lock.json` committed, `packageManager` pinned).
- **Recommendation:** adopt **uv** (the de-facto standard Python project manager in 2026 — see Sources) with a committed `uv.lock`; it replaces `pip` + `venv` with one faster tool and gives the Docker build `uv sync --frozen` reproducibility. If staying on pip, at minimum commit a `pip-compile`-style pinned requirements file used by the Dockerfile.
- `python:3.12-slim` and `postgres:17-alpine` are pinned to majors only. Fine for a laptop app; pin minors/digests only if reproducibility becomes a real concern.

### 2.4 Google Fonts from CDN (also an offline-first defect)

`frontend/src/index.html` loads Roboto and Material Icons from `fonts.googleapis.com` (the stock `ng add @angular/material` output). Two problems:
1. **It contradicts the design's own offline-first goal** (NFR-OFF-01/02, Lighthouse PWA ≥ 90 in M5): with the app shell cached but fonts remote, offline rendering falls back and icon fonts break.
2. Every page load pings Google — a (mild) privacy leak for a purely self-hosted app.

**Recommendation:** self-host the fonts (e.g. Fontsource packages, bundled by the Angular build) — cheap to do now, mandatory by M5 anyway. This is a case where the generated default should not survive contact with this particular design doc.

---

## 3. `.gitignore` review

Current state is mostly correct (verified: `.env`s, `.pytest_cache/`, `node_modules/`, `.angular/cache`, `out-tsc` all properly ignored). Gaps and oddities:

| Item | Finding |
|------|---------|
| `.DS_Store` | ✅ **Done 2026-07-12** — added to the root `.gitignore`. (Was only ignored under `frontend/`; on macOS these appear everywhere.) |
| Root `.env` | ✅ **Done 2026-07-12** — root `.env.example` added (DB credentials, `CORS_ALLOWED_ORIGINS`, incl. the LAN-origin example) and the README's quick-start now explains the Compose-reads-it mechanism and the difference from `backend/.env`. |
| `.claude/*` | Blanket-ignores `.claude/skills/implement-pr/SKILL.md`, which `CLAUDE_IMPROVEMENTS.md` itself flags as worth sharing. Add `!.claude/skills/` if the skill should survive a re-clone; as-is it exists only on this machine. |
| `scripts/` | Ignored at root, but no such directory exists and nothing explains it (it's a local-scratch convention). Either add a comment in `.gitignore` or rename the convention to something self-explanatory (`scratch/`). Ignoring a plausibly-committable name like `scripts/` will eventually surprise someone who tries to commit a real script. |
| `backend/.gitignore` | Fine. ✅ `.ruff_cache/` added 2026-07-12 together with Ruff (see §4). |

---

## 4. Tool choices — verdicts

Checked against the ecosystem as of July 2026:

| Choice | Verdict | Notes |
|--------|---------|-------|
| FastAPI + Pydantic v2 + SQLAlchemy 2.x + Alembic | ✅ Correct | Current, healthy, standard stack. FastAPI floor `>=0.115` is old (current: 0.139) but harmless *once a lockfile exists* (2.3). |
| **pyright strict** | ✅ Correct | The PR3 rationale (same engine as Pylance, editor = gate) is sound and matches the no-CI workflow. |
| **`httpx2`** | ✅ Correct — and ahead of the curve | Verified: `httpx2` is Pydantic's maintained fork of the stalled httpx; Starlette's TestClient now prefers it and deprecates plain httpx. The repo (and its memory note) made the right call. |
| pip + venv | ✅ Resolved — migrated to uv 2026-07-12 | uv is the 2026 default for new projects: lockfile, speed, one tool. See 2.3 (resolved). |
| **No Python linter/formatter** | ✅ Resolved 2026-07-12 | **Ruff** added (lint + format; rules E/F/W/I/UP/B/C4/RUF, line-length 100): `make lint`/`format-check` are part of `make check`, and `.githooks/pre-commit` now guards staged backend files too — the hook previously only covered `frontend/`, quietly contradicting the "checks are the gate for every change" rule. Existing code was already clean (zero lint findings; three lines rewrapped). |
| Angular 22, standalone, zoneless, signals | ✅ Current | 22.0.x is the latest stable (July 2026). `provideZonelessChangeDetection` + signal-based root is exactly the modern default. |
| Vitest via `@angular/build:unit-test` | ✅ Correct | The current Angular default runner; Karma is dead. |
| Angular Material | ✅ Per design | Dependency lands in M0 while unused until M3 — the milestone doc explicitly ordered this, so fine; just don't let the theme drift before M3. |
| npm (`packageManager` pinned) | ✅ Fine | No reason to switch. |
| PostgreSQL 17 | ⚠️ One major behind | PG 18 has been stable since Sept 2025 (18.4 current). 17 is supported into 2029, so no urgency — but a project with **zero domain tables** will never have a cheaper upgrade than today. Note: PG 18's image changed the volume path (`/var/lib/postgresql` instead of `.../data`), so the compose volume mapping must change with the bump. |
| Python 3.12 (image + pyright `pythonVersion`) | ⚠️ Inconsistent with reality | The local dev environment runs 3.14 (per project memory), while the image and the type-check certify 3.12. Whatever runs locally is *not* what pyright checks or what ships. Align all three — either pin local dev to 3.12, or (better, since nothing here needs 3.12 specifically) bump image + `pythonVersion` to 3.13/3.14. |
| Docker Compose (healthchecks, named volume, `depends_on: service_healthy`, migrations-on-start) | ✅ Well done | Aside from the port-binding issue (1.3). Consider `restart: unless-stopped` for the laptop use-case so the stack survives reboots. |

---

## 5. Disagreements with documented decisions

The docs asked for a candid check, so: places where this review thinks a documented decision is wrong (or wrongly scheduled), even though it *was* deliberate.

### 5.1 Hard-coding the LAN IP into the Angular build (§8) — the weakest design decision in the doc

The design hard-codes `http://192.168.1.10:8000/api/v1` into `environment.ts` and defers the same-origin reverse proxy to Future Work "because the proxy needs hands-on reverse-proxy familiarity first". Disagreement:

- Laptop LAN IPs are typically **DHCP-assigned**. Every lease change means editing `environment.ts`, rebuilding the frontend, *and* updating `CORS_ALLOWED_ORIGINS`. That is three coupled moving parts for the app's most basic wiring.
- The deferred alternative is *simpler*, not harder, than what it replaces: one Caddy (or nginx) container in the existing Compose file, serving the built frontend and proxying `/api/*`. ~15 lines of config. It **deletes** the CORS configuration, the rebuild-to-repoint problem, and most of finding 2.1's exposure in one move.
- The cost of the current approach starts being paid in **M3** (first real frontend↔backend traffic), not at some later date.

**Recommendation:** pull "Same-origin reverse proxy" forward from Future Work to M3 (or M5 at the latest, where the PWA's HTTPS/installability pressures compound the issue). Failing that, use the laptop's mDNS name (`something.local`) instead of a raw IP to at least survive DHCP.

### 5.2 "No CI provider in use" is no longer true

`FUTURE_WORK_V1.md` defers CI because "there is no CI provider in use" — but the repo lives on **GitHub** (`origin` = github.com, PRs are merged via `gh`). GitHub Actions is available for free at this repo's scale. The entire local gate already exists as one command (`make check`); a ~20-line workflow running it on PRs would turn "discipline" into "guarantee" at near-zero cost. The no-CI stance made sense when written; the premise has since expired. Recommend revisiting rather than waiting for Future Work.

### 5.3 Postgres over SQLite — accepted, with a note

The design considered SQLite and confirmed Postgres, and the data-access layering makes the engine swappable, so this review does not contest the decision. It is worth recording, though, that **most of M0's operational surface** — Docker, Compose, the exposed port (finding 1.3), credentials, volumes, `pg_isready`, migrations-vs-running-DB sequencing — exists *because* of that choice, for a single-user app whose write volume is a few rows a day. If operational friction ever becomes a complaint, this is the root cause, and the design's own §2 note says the switch stays cheap.

### 5.4 Version numbering — ✅ resolved

*(Resolved 2026-07-12: both bumped to `0.1.0`, and a versioning policy is now written down in the README — SemVer at the application level, minor bump per milestone pre-1.0, `1.0.0` reserved for REQUIREMENTS_V1 fully implemented, `/api/v1` contract version independent.)*

`pyproject.toml` and the FastAPI app both declare `version = "1.0.0"` for a milestone that is explicitly "structure without behaviour". Semantically this should be `0.x` until the app does something; `1.0.0` will make future "what changed since 1.0?" questions unanswerable. Trivial now, annoying later.

### 5.5 Where the docs got it right

For balance: decisions this review pressure-tested and endorses — the milestone-scoped stub discipline (empty modules with docstrings are the right amount of M0); PR5's error envelope landing in M0 (the doc's own "judgment call" note is honest, and having every future endpoint born inside the envelope is worth it); client-minted UUIDs for idempotency (§5.5) instead of an idempotency-key header; the watched-only library invariant (§5.3); and pyright-over-mypy for an editor-driven, no-CI workflow.

---

## 6. Is everything that was implemented needed?

Short answer: yes — M0 contains remarkably little fat. The empty stubs are all mandated by the milestone doc and each carries a docstring explaining what arrives when. Items that *are* questionable:

| Item | Assessment |
|------|-----------|
| `backend/migrations/.gitkeep`, `backend/tests/.gitkeep` | Obsolete — both directories have real tracked files now. Delete. |
| `frontend/README.md` | Stock `ng new` boilerplate; even documents `ng e2e`, which isn't configured. Either trim to a pointer at the root README or delete. |
| `CLAUDE_IMPROVEMENTS.md` at repo root | ✅ **Addressed 2026-07-12** — moved to `improvements/` (together with this review). |
| `frontend/src/app/core/route-registry.ts` vs `routes.registry.ts` | Both needed (infrastructure vs. append-only data) — but the names differ by one transposed word and a separator style. A future contributor *will* open the wrong one. Suggest `route-registry.ts` + `route-registry.data.ts` (or fold the empty array into the infra file until M3 needs it). |
| Missing: `app/adapters/` | ✅ **Resolved 2026-07-12** — decided the *other* way: no stub folder; adapters are future-if-ever, and the layering (core never imports an adapter) is what keeps them hook-in-able. DESIGN §4 tree + §5.6 note, milestone §3 + PR1 scope, and `backend/CLAUDE.md` all annotated accordingly. |
| Missing: `LICENSE` | The repo is on GitHub with no license file — if the repo is (or ever becomes) public, that means "all rights reserved" by default. Add one deliberately, or note that it's intentionally private. |

---

## 7. Smaller findings (docs & consistency)

1. **Milestone doc status**: `MILESTONE_M0_V1.md` still says `Status: Draft`, and the §2 Definition-of-Done checkboxes are all unchecked — while every PR below is ✅-complete with verification notes. Flip the exit-criteria boxes and mark the milestone done; the doc is the record of M0 having actually exited.
2. **`rewatch/` has no `dependencies.py`** while the four CRUD modules do. Defensible (§4 describes rewatch differently), but worth one line in a docstring so it reads as intent, not omission.
3. **DESIGN §3 typo**: "…the list is only as current as the last successful backend connection (§6.2) —  refreshes it." — a word is missing before "refreshes" (presumably "reopening the view").
4. **`conftest.py`'s cached-settings interplay**: `get_settings()` is `lru_cache`d; today's tests are fine, but the first M1 test that wants *different* settings will silently get the cached ones. A `get_settings.cache_clear()` fixture (or DI override) will be needed — noting it now saves a debugging session later.
5. **Compose default `CORS_ALLOWED_ORIGINS`** only covers `http://localhost:4200`; fine for M0, but the LAN origin the whole §8.2 story depends on has to be supplied by hand every `up`. ✅ Done 2026-07-12 — documented (with the LAN-origin example) in the new root `.env.example`.
6. **Production build ships the placeholder IP**: `ng build` defaults to production, which bakes in the fictional `192.168.1.10`. Anyone running the production bundle before editing `environment.ts` gets silent request failures. A loud placeholder (`http://CHANGE-ME...`) would fail obviously instead.

---

## 8. Overall verdict

M0's *stated* goal — structure without behaviour, strictness from the first commit, one-command run — is genuinely met, and the execution quality of the code that exists is high (typed everywhere, tested where testable, documented beyond the norm). The findings that matter are repository-level: the requirements doc (1.1, ✅ restored same day), the `node_modules` history bloat (1.2, ✅ scrubbed and force-pushed same day), stop publishing Postgres to the LAN (1.3, ✅ loopback-bound 2026-07-12), and give the backend the same lockfile + lint discipline the frontend already has (2.3 + 4, ✅ uv + Ruff 2026-07-12). The remaining items don't block M1, but they get more expensive with every milestone that passes.

---

## Sources

- [Starlette release notes — TestClient on httpx2](https://starlette.dev/release-notes/) · [Starlette PR #3291 — Support httpx2 in the test client](https://github.com/Kludex/starlette/pull/3291) · [FastAPI discussion — httpx deprecated for TestClient](https://github.com/fastapi/fastapi/discussions/15742)
- [Angular releases / versioning](https://angular.dev/reference/releases) · [Angular version history & EOL](https://www.herodevs.com/blog-posts/angular-version-history-every-release-date-support-window-and-end-of-life-date-from-angularjs-to-angular-22)
- [PostgreSQL 18 announcement](https://www.postgresql.org/about/news/postgresql-18-released-3142/) · [postgres Docker image (PG18 volume-path change)](https://hub.docker.com/_/postgres) · [Best practices for Postgres in Docker (2026)](https://sliplane.io/blog/best-practices-for-postgres-in-docker)
- [FastAPI release notes](https://fastapi.tiangolo.com/release-notes/) · [fastapi on PyPI](https://pypi.org/project/fastapi/)
- [uv vs pip — Real Python](https://realpython.com/uv-vs-pip/) · [Python package managers in 2026](https://scopir.com/posts/best-python-package-managers-2026/)
- [Ruff](https://github.com/astral-sh/ruff) · [Ruff — complete guide](https://pydevtools.com/handbook/explanation/ruff-complete-guide/)
