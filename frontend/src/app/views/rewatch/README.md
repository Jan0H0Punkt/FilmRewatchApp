# `views/rewatch/`

The Rewatch Suggestion view (REQ §7.1, DESIGN §6.3) — a responsive card grid of
the films currently due for a rewatch, most overdue first. A primary navigation
destination and the app's landing route (§6.5).

The view holds no rules: `domain/rewatch/` joins the due-list to the cached
film metadata and shapes the cards, and also runs the one filter this view
has — a "done watching by" time picker that hides a film whose runtime
would run past the chosen clock time if started now. Ordering is the
algorithm's and is never re-sorted here (FR-RW-04). There is no refresh
control by design (§7.1) — the backend recomputes once a day, and a film the
user has just watched is removed from the list immediately by the facade
(§6.3).

Not built yet: filtering the list by tag/genre/director, which DESIGN §6.3
marks as future work, not first release.
