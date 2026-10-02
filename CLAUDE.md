# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Orientation

FilmRewatchApp is a two-tier film-tracking app: an Angular PWA client and a FastAPI backend, communicating over a versioned `/api/v1` HTTP/JSON API.

It is a monorepo with **per-tier guidance** — when working inside a tier, read that tier's `CLAUDE.md` for its commands, architecture, and conventions:

- **`backend/CLAUDE.md`** — the FastAPI backend (layering, `core/`, migrations, strict typing).
- **`frontend/CLAUDE.md`** — the Angular client (strict TS, §6.1 layering, route registry, `environment.ts` wiring).

## Todo list

At the start of every conversation, read the root `todo.md` and tell Jan which open todos are in it before doing anything else. Each bullet is a todo with a 1–3 sentence description.

## Design-doc-driven

Development is **design-doc-driven**. Before writing feature code, read the relevant sections of `docs/`:

- `docs/designs/DESIGN_V1.md` — the authoritative technical design. Code and commit messages reference its sections (`§5.1`, `§5.7`) and requirement IDs (`NFR-MAINT-03`, `FR-LIB-04`) pervasively; keep doing so.
- `docs/requirements/REQUIREMENTS_V1.md`, `docs/requirements/OPEN_DECISIONS_V1.md`, `docs/requirements/FUTURE_WORK_V1.md`.

**The core domain (M1) and the rewatch engine (M4), scoring included, are built.** The milestone documents for those are gone — the code is the record. What is still open is listed in `docs/requirements/OPEN_DECISIONS_V1.md`, ordered by the milestone it is due at, and in the root `todo.md`. Do not add logic to a milestone that doesn't own it. This discipline applies to **both tiers**.

## Workflow

There is no CI — type-checks and tests are run **locally** and are the gate for every change. Strict type-safety (§5.7) is enforced from the first commit on both tiers (pyright strict on the backend, strict TypeScript on the frontend); treat a type error as a build break. Each tier's `CLAUDE.md` lists the concrete commands.
