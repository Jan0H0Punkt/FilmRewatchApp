# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Orientation

FilmRewatchApp is a two-tier film-tracking app: an Angular PWA client and a FastAPI backend, communicating over a versioned `/api/v1` HTTP/JSON API. Only the **backend** exists so far; the Angular workspace is not yet created.

It is a monorepo with **per-tier guidance** — when working inside a tier, read that tier's `CLAUDE.md` for its commands, architecture, and conventions:

- **`backend/CLAUDE.md`** — the FastAPI backend (layering, `core/`, migrations, strict typing).
- **`frontend/CLAUDE.md`** — the Angular client. *Not present yet — created in M0 PR7.*

## Design-doc-driven & milestone-sequenced

Development is **design-doc-driven and milestone-sequenced**. Before writing feature code, read the relevant sections of `docs/`:

- `docs/designs/DESIGN_V1.md` — the authoritative technical design. Code and commit messages reference its sections (`§5.1`, `§5.7`) and requirement IDs (`NFR-MAINT-03`, `FR-LIB-04`) pervasively; keep doing so.
- `docs/milstones/MILESTONE_M0_V1.md` — the current milestone (M0, "Scaffolding"), broken into per-PR work items with acceptance criteria and an explicit out-of-scope list.
- `docs/requierements/REQUIEREMENTS_V1.md` (note the spelling), `docs/requierements/OPEN_DECISIONS_V1.md`, `docs/requierements/FUTURE_WORK_V1.md`.

**The repo is currently in M0.** M0 delivers *structure without behaviour*: the layout exists, but there is no domain logic, no ORM tables, and no real screens or routes — those arrive in M1+. Do not add logic to a milestone that doesn't own it (see the out-of-scope table in the milestone doc). This discipline applies to **both tiers**.

## Workflow

There is no CI — type-checks and tests are run **locally** and are the gate for every change. Strict type-safety (§5.7) is enforced from the first commit on both tiers (pyright strict on the backend, strict TypeScript on the frontend); treat a type error as a build break. Each tier's `CLAUDE.md` lists the concrete commands.
