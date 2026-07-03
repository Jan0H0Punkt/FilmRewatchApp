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
| 2 | `frontend/node_modules` was committed into `main`'s history — `.git` is ~98 MB for a scaffolding repo | **High** |
| 3 | Postgres is published on `0.0.0.0:5432` with default credentials — reachable by anyone on the LAN | **High (security)** |
| 4 | The API has no authentication and is deliberately LAN-exposed — nowhere recorded as an accepted risk | Medium (security) |
| 5 | Backend has no dependency lockfile and no linter/formatter (frontend has both) | Medium |
| 6 | Google Fonts loaded from CDN — contradicts the offline-first PWA goal | Medium |
| 7 | Root `.gitignore` gaps (`.DS_Store`, undocumented root `.env`, un-shareable `.claude/skills/`) | Low |
| 8 | Assorted doc/code mismatches (missing `app/adapters/`, milestone doc still "Draft", stock frontend README) | Low |

Details, evidence, and recommendations below.

---

## 1. High-priority findings

### 1.1 The requirements document was missing from `main` — ✅ resolved

*(Resolved 2026-07-03, same day as the review.)* `CLAUDE.md`, `README.md`, `DESIGN_V1.md`, `FUTURE_WORK_V1.md`, and `MILESTONE_M0_V1.md` all linked to `docs/requirements/REQUIEREMENTS_V1.md`, but the file did not exist on `main` — it was lost when the docs were reorganised, surviving only on the unmerged branches `origin/plan/design_v1` and `origin/requierements_and_planing`. For a repo whose stated methodology is *design-doc-driven* with requirement IDs (`FR-LIB-04`, `NFR-MAINT-03`) cited throughout code and commits, the root of that traceability chain being absent was the single most important defect in M0.

**Resolution:** the file (v1.1, "Approved", 814 lines — verified content-identical to the `origin/plan/design_v1` copy) was restored as **`docs/requirements/REQUIREMENTS_V1.md`**, fixing the long-standing filename typo in the same move. All references across the five linking docs were updated, the in-file relative link to `DESIGN_V1.md` was corrected for the new location, and recovery artifacts (a stray diff hunk-header line, a missing trailing newline) were cleaned. Not yet committed at the time of writing.

### 1.2 `node_modules` is baked into git history

Commit `c58a3284` ("dummy frontend") and follow-ups (`7729caf2`, `1cedc009`) committed `frontend/node_modules` — and those commits are **reachable from `main`**. Result: `.git` weighs ~98 MB for a repo whose working tree is a few hundred KB. Every clone pays this forever, and it will only compound.

**Recommendation:** decide now, while the repo has one contributor:
- **Rewrite history** with `git filter-repo --path frontend/node_modules --invert-paths` (or BFG), force-push, re-clone. Cheap today, painful later. This is the right call for a young solo repo.
- Or explicitly accept the bloat and note it — but do it as a decision, not by default.

Also: the stale branches `origin/plan/design_v1`, `origin/requierements_and_planing`, and local `feat/m0` / `pr-4` should be deleted once anything still needed from them (see 1.1!) is recovered.

### 1.3 Postgres is exposed to the whole LAN with default credentials

`docker-compose.yml` publishes `"5432:5432"`, which binds `0.0.0.0` — and the deployment target is a laptop that is *deliberately* on shared Wi‑Fi (that's how the phone reaches the backend). Combined with the default `filmrewatch`/`filmrewatch` credentials, **anyone on the same network can connect to the database with superuser rights on it**. The port is published only so host-side tooling (`psql`, Alembic) can reach the DB — that need is fully served by a loopback bind.

**Recommendation:** change the mapping to `"127.0.0.1:5432:5432"`. This is a one-line fix with zero workflow cost: the backend container reaches Postgres over the Compose network (unaffected), and host tools use localhost. The backend's `8000` port must stay LAN-exposed (the PWA needs it); Postgres must not.

Two smaller issues in the same file:
- The Postgres healthcheck hardcodes `pg_isready -U filmrewatch` — if `POSTGRES_USER` is ever overridden, the healthcheck lies. Use `${POSTGRES_USER:-filmrewatch}` (Compose interpolates healthcheck args).
- The backend healthcheck hardcodes port `8000`; overriding `PORT` would break it. Acceptable as-is, but worth a comment.

---

## 2. Security review (rest)

### 2.1 Unauthenticated, LAN-reachable write API — record the *exposure*, not just the scoping

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

### 2.3 Supply chain / reproducibility

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
| `.DS_Store` | Only ignored under `frontend/` (the CLI-generated file). On macOS these appear everywhere — add `.DS_Store` to the **root** `.gitignore`. |
| Root `.env` | Ignored (good) but **undocumented**: `docker-compose.yml` reads `POSTGRES_USER`/`POSTGRES_PASSWORD` from it, yet there is no root `.env.example` and the README never mentions it. Add a root `.env.example` (NFR-MAINT-04's own logic demands it). |
| `.claude/*` | Blanket-ignores `.claude/skills/implement-pr/SKILL.md`, which `CLAUDE_IMPROVEMENTS.md` itself flags as worth sharing. Add `!.claude/skills/` if the skill should survive a re-clone; as-is it exists only on this machine. |
| `scripts/` | Ignored at root, but no such directory exists and nothing explains it (it's a local-scratch convention). Either add a comment in `.gitignore` or rename the convention to something self-explanatory (`scratch/`). Ignoring a plausibly-committable name like `scripts/` will eventually surprise someone who tries to commit a real script. |
| `backend/.gitignore` | Fine. Consider adding `.ruff_cache/` when ruff lands (see 4.2). |

---

## 4. Tool choices — verdicts

Checked against the ecosystem as of July 2026:

| Choice | Verdict | Notes |
|--------|---------|-------|
| FastAPI + Pydantic v2 + SQLAlchemy 2.x + Alembic | ✅ Correct | Current, healthy, standard stack. FastAPI floor `>=0.115` is old (current: 0.139) but harmless *once a lockfile exists* (2.3). |
| **pyright strict** | ✅ Correct | The PR3 rationale (same engine as Pylance, editor = gate) is sound and matches the no-CI workflow. |
| **`httpx2`** | ✅ Correct — and ahead of the curve | Verified: `httpx2` is Pydantic's maintained fork of the stalled httpx; Starlette's TestClient now prefers it and deprecates plain httpx. The repo (and its memory note) made the right call. |
| pip + venv | ⚠️ Works, but dated | uv is the 2026 default for new projects: lockfile, speed, one tool. See 2.3. |
| **No Python linter/formatter** | ❌ Gap | The frontend has ESLint + Prettier + a pre-commit hook; the backend has *nothing* between "pyright passes" and "whatever style". **Ruff** (lint + format, one tool) is the de-facto standard and used by FastAPI/Pydantic themselves. Add it and extend `.githooks/pre-commit` to cover staged backend files — right now the hook only guards `frontend/`, which quietly contradicts the "checks are the gate for every change" rule. |
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

### 5.4 Version numbering

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
| `CLAUDE_IMPROVEMENTS.md` at repo root | Useful content, wrong place — it's a tooling/DX backlog that self-describes as "not a product design doc", yet sits at top level beside the README. Move under `docs/` or `.claude/`. |
| `frontend/src/app/core/route-registry.ts` vs `routes.registry.ts` | Both needed (infrastructure vs. append-only data) — but the names differ by one transposed word and a separator style. A future contributor *will* open the wrong one. Suggest `route-registry.ts` + `route-registry.data.ts` (or fold the empty array into the infra file until M3 needs it). |
| Missing: `app/adapters/` | The reverse problem — something the docs say exists, doesn't. DESIGN §4 and milestone PR1's in-scope list both include `app/adapters/` stubs, and `backend/CLAUDE.md` speaks of it in the present tense ("`app/adapters/` … is deliberately **not** mounted"). Either create the stub folder or amend the three docs. As-is, the first M-milestone that touches adapters will discover the docs describe a fiction. |
| Missing: `LICENSE` | The repo is on GitHub with no license file — if the repo is (or ever becomes) public, that means "all rights reserved" by default. Add one deliberately, or note that it's intentionally private. |

---

## 7. Smaller findings (docs & consistency)

1. **Milestone doc status**: `MILESTONE_M0_V1.md` still says `Status: Draft`, and the §2 Definition-of-Done checkboxes are all unchecked — while every PR below is ✅-complete with verification notes. Flip the exit-criteria boxes and mark the milestone done; the doc is the record of M0 having actually exited.
2. **`rewatch/` has no `dependencies.py`** while the four CRUD modules do. Defensible (§4 describes rewatch differently), but worth one line in a docstring so it reads as intent, not omission.
3. **DESIGN §3 typo**: "…the list is only as current as the last successful backend connection (§6.2) —  refreshes it." — a word is missing before "refreshes" (presumably "reopening the view").
4. **`conftest.py`'s cached-settings interplay**: `get_settings()` is `lru_cache`d; today's tests are fine, but the first M1 test that wants *different* settings will silently get the cached ones. A `get_settings.cache_clear()` fixture (or DI override) will be needed — noting it now saves a debugging session later.
5. **Compose default `CORS_ALLOWED_ORIGINS`** only covers `http://localhost:4200`; fine for M0, but the LAN origin the whole §8.2 story depends on has to be supplied by hand every `up`. Once a root `.env.example` exists (finding 3), document it there.
6. **Production build ships the placeholder IP**: `ng build` defaults to production, which bakes in the fictional `192.168.1.10`. Anyone running the production bundle before editing `environment.ts` gets silent request failures. A loud placeholder (`http://CHANGE-ME...`) would fail obviously instead.

---

## 8. Overall verdict

M0's *stated* goal — structure without behaviour, strictness from the first commit, one-command run — is genuinely met, and the execution quality of the code that exists is high (typed everywhere, tested where testable, documented beyond the norm). The findings that matter are repository-level: the requirements doc (1.1, ✅ restored same day), scrub `node_modules` from history while it's cheap (1.2), stop publishing Postgres to the LAN (1.3), and give the backend the same lockfile + lint discipline the frontend already has (2.3, 4). None of these blocks M1, but they get more expensive with every milestone that passes.

---

## Sources

- [Starlette release notes — TestClient on httpx2](https://starlette.dev/release-notes/) · [Starlette PR #3291 — Support httpx2 in the test client](https://github.com/Kludex/starlette/pull/3291) · [FastAPI discussion — httpx deprecated for TestClient](https://github.com/fastapi/fastapi/discussions/15742)
- [Angular releases / versioning](https://angular.dev/reference/releases) · [Angular version history & EOL](https://www.herodevs.com/blog-posts/angular-version-history-every-release-date-support-window-and-end-of-life-date-from-angularjs-to-angular-22)
- [PostgreSQL 18 announcement](https://www.postgresql.org/about/news/postgresql-18-released-3142/) · [postgres Docker image (PG18 volume-path change)](https://hub.docker.com/_/postgres) · [Best practices for Postgres in Docker (2026)](https://sliplane.io/blog/best-practices-for-postgres-in-docker)
- [FastAPI release notes](https://fastapi.tiangolo.com/release-notes/) · [fastapi on PyPI](https://pypi.org/project/fastapi/)
- [uv vs pip — Real Python](https://realpython.com/uv-vs-pip/) · [Python package managers in 2026](https://scopir.com/posts/best-python-package-managers-2026/)
- [Ruff](https://github.com/astral-sh/ruff) · [Ruff — complete guide](https://pydevtools.com/handbook/explanation/ruff-complete-guide/)
