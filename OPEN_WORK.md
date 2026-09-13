# Open Work

Deferred technical/dev tasks — not product scope (that's `docs/requirements/FUTURE_WORK_V1.md`). Add a row when something's worth doing but not now; delete the row once it's done.

| Task | Description | Priority | Created |
|---|---|---|---|
| Decide the rewatch algorithm's rule for unrated films | FR-RW-02 passes `average_rating` to the M4 algorithm and promised it was always present; since FR-RAT-12 it can be `null` (a film whose every watch is unrated). Pick one before building §5.8: treat as the library average, exclude from suggestions, or use a neutral constant. `app/rewatch/` is still an empty stub, so nothing is broken today. | Medium | 2026-09-13 |
| Split `backend/app/films/service.py` | File is 282 lines, over the ~200-line escape-hatch threshold in `backend/CLAUDE.md`. Split into `app/films/service/` per the new subfolder convention (`orchestration.py`, `validation.py`, `errors.py`). | Low | 2026-09-11 |
