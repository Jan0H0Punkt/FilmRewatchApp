# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Orientation

FilmRewatchApp is a two-tier film-tracking app: an Angular PWA client and a FastAPI backend, communicating over a versioned `/api/v1` HTTP/JSON API.

It is a monorepo with **per-tier guidance** — when working inside a tier, read that tier's `CLAUDE.md` for its commands, architecture, and conventions:

- **`backend/CLAUDE.md`** — the FastAPI backend (layering, `core/`, migrations, strict typing).
- **`frontend/CLAUDE.md`** — the Angular client (strict TS, §6.1 layering, route registry, `environment.ts` wiring).

## Design-doc-driven & milestone-sequenced

Development is **design-doc-driven and milestone-sequenced**. Before writing feature code, read the relevant sections of `docs/`:

- `docs/designs/DESIGN_V1.md` — the authoritative technical design. Code and commit messages reference its sections (`§5.1`, `§5.7`) and requirement IDs (`NFR-MAINT-03`, `FR-LIB-04`) pervasively; keep doing so.
- `docs/milestones/MILESTONE_M1_V1.md` — the current milestone (M1, "Core domain"), broken into per-PR work items with acceptance criteria and an explicit out-of-scope list.
- `docs/requirements/REQUIREMENTS_V1.md`, `docs/requirements/OPEN_DECISIONS_V1.md`, `docs/requirements/FUTURE_WORK_V1.md`.

**The repo is currently in M1**, which builds the core domain (films, ratings, tags, genres) on M0's scaffolding. Do not add logic to a milestone that doesn't own it (see the out-of-scope table in the milestone doc). This discipline applies to **both tiers**.

## Workflow

There is no CI — type-checks and tests are run **locally** and are the gate for every change. Strict type-safety (§5.7) is enforced from the first commit on both tiers (pyright strict on the backend, strict TypeScript on the frontend); treat a type error as a build break. Each tier's `CLAUDE.md` lists the concrete commands.
