# Open Work

Deferred technical/dev tasks — not product scope (that's `docs/requirements/FUTURE_WORK_V1.md`). Add a row when something's worth doing but not now; delete the row once it's done.

| Task | Description | Priority | Created |
|---|---|---|---|
| Split `backend/app/films/service.py` | File is 282 lines, over the ~200-line escape-hatch threshold in `backend/CLAUDE.md`. Split into `app/films/service/` per the new subfolder convention (`orchestration.py`, `validation.py`, `errors.py`). | Low | 2026-09-11 |
| Search films by director (FR-SF-02) | The Library search matches titles only. Director is the second criterion the requirements name: one more field on `LibraryCriteria` plus one `PREDICATES` entry in `frontend/src/app/views/library/filters.ts` — the FR-EXT-05 seam, so the view stays untouched. (REQUIREMENTS §5.4, DESIGN §7.2.) | Low | 2026-09-19 |
