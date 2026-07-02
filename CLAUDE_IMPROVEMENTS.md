# Claude Code Setup — Improvement Backlog

**Created:** 2026-07-02
**Basis:** Assessment of this repo's `CLAUDE.md` files and Claude Code configuration against the official docs — [Memory](https://code.claude.com/docs/en/memory) and [Best practices](https://code.claude.com/docs/en/best-practices).

This is a tooling/DX backlog for how effectively Claude Code works in this repo. It is **not** a product design doc — it does not belong to a milestone.

---

## Baseline — already best-practice ✅

Little to fix in the `CLAUDE.md` files themselves; the static context footprint is already minimal.

- `CLAUDE.md` (root) **26 lines**, `backend/CLAUDE.md` **57 lines** — both far under the documented **"target under 200 lines"** limit.
- Monorepo split matches the documented pattern: **root loads every session; a subdirectory `CLAUDE.md` loads on-demand** when Claude reads files in that directory.
- Structure (headers/bullets), specificity (concrete commands + paths), and no cross-file contradictions.
- Content is on the docs' **"include"** side (unguessable commands, non-obvious gotchas, architecture, env quirks) and avoids the **"exclude"** side (inferable facts, file-by-file dumps).
- **Auto-memory is active** at `~/.claude/projects/<repo>/memory/` (`MEMORY.md` index + topic files) — the documented shape.

**Doc facts to keep in mind (no action needed):**
- `@path` imports do **not** save tokens — imported files load in full at launch. Use them for organization only.
- Root `CLAUDE.md` survives `/compact`; **nested `CLAUDE.md` files are not re-injected** after compaction until Claude next reads a file in that subdirectory.

---

## Improvements (prioritized)

### 1. Permission allowlist — ✅ _done_
- [x] Allowlist the safe commands run every session so approvals stop interrupting: `make typecheck`, `make test`, `pytest`, `git diff`/`status`/`log`, `grep`, `ls`, etc.
- **Why:** removes repeated approval friction on known-safe dev commands.
- **How:** run the `/fewer-permission-prompts` skill, or add rules to `.claude/settings.json`. A `.claude/settings.local.json` already exists to build on.
- **Status:** Added `Bash(make typecheck)` and `Bash(make test)` to `.claude/settings.json` (new, shared, now trackable after `.gitignore` fix). Analysis found most frequent commands (`python3 scripts/*`, `cd`, `source .venv…`) are either arbitrary code execution or already auto-allowed, so minimal safe entries exist. Also: saved preference to use `python3.14` instead of stale system `python3` in memory (`use-python3.14.md`). **Effort:** S · **Risk:** low.

### 2. Path-scoped rules (`.claude/rules/`) — _when guidance grows_
- [ ] Move narrow, area-specific guidance into rules with `paths:` frontmatter so it loads **only** when Claude opens matching files (the docs' headline token-saver).
- **Candidates:** `paths: ["backend/migrations/**"]` for Alembic specifics; `paths: ["backend/app/**/*.py"]` for backend coding rules once the frontend lands.
- **Why:** keeps per-area detail out of the always-on context.
- **Not needed yet** — current files are small; reach for this when a `CLAUDE.md` approaches the 200-line limit.
- **Effort:** S–M.

### 3. Skill for the repeatable PR workflow — ✅ _done_
- [x] Encode the "implement PR N from `docs/milestones/MILESTONE_M0_V1.md`" loop as a `.claude/skills/<name>/SKILL.md`.
- **Why:** skills load **on-demand**, keeping the workflow out of the always-loaded `CLAUDE.md`; invokable as `/skill-name`.
- **Status:** Created `.claude/skills/implement-pr/SKILL.md` (`disable-model-invocation: true`, invoke as `/implement-pr <PR-number>`). It captures the full loop: read the work item + design refs, respect out-of-scope, study conventions, implement per the layered architecture, run the `make typecheck`/`make test` gate (venv-activated, `python3.14`), and update the milestone doc with the same ✅/annotation formatting as the completed PRs.
- **⚠ Sharing:** currently git-ignored (`.claude/skills` is caught by `.claude/*`), so it works locally but isn't committed/shared. To team-share it, add a `.gitignore` negation like `!.claude/skills/` (see item in Housekeeping).
- **Effort:** M.

### 4. Behavioral habits — _free, no setup_
- [ ] `/clear` between unrelated tasks to reset context (avoids the "kitchen-sink session").
- [ ] "Use a subagent to investigate X" for wide codebase searches — exploration runs in a separate context and reports back a summary, keeping the main window clean.
- **Why:** context is the fundamental constraint; performance degrades as it fills.

### 5. Optional — deterministic typecheck gate (hook)
- [ ] A `PostToolUse`/`Stop` hook that runs `make typecheck` after Python edits, turning the advisory "strict types are the gate" rule into an enforced one.
- **Why:** hooks are deterministic (run regardless of what Claude decides); `CLAUDE.md` is advisory.
- **Trade-off:** heavier setup + slows the edit loop — adopt only if type regressions slip through.
- **Effort:** M.

---

## Housekeeping (tracked elsewhere, noted here for completeness)
- The **"repo is in M0"** note in both `CLAUDE.md` files is time-varying — bump it at each milestone boundary (M0 → M1 …).
- **`frontend/CLAUDE.md`** is intentionally absent — create it with **M0 PR7** (Angular workspace).
- ✅ **Spelling fixed:** renamed `docs/milstones/` → `docs/milestones/` and `docs/requierements/` → `docs/requirements/` throughout (via `git mv` + `sed`). Updated all references in `CLAUDE.md` files, `CLAUDE_IMPROVEMENTS.md`, and inter-doc links.
