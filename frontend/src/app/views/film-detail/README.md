# `views/film-detail/`

The Film Detail view (`film/:id`, REQ §7.3), reached contextually by selecting
a film — not a primary navigation destination (DESIGN §6.5). Read-only
metadata, rating history actions, the favourite toggle, rewatch delay, Delete
Film, and inline tag/genre editing are all built.

The Edit form (`films/:id/edit`) is a separate plan item and is deliberately
not built here — there is no Edit control on this view yet.
