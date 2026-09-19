# `views/film-detail/`

The Film Detail view (`film/:id`, REQ §7.3), reached contextually by selecting
a film — not a primary navigation destination (DESIGN §6.5). Read-only
metadata, rating history actions, the favourite toggle, rewatch delay, Delete
Film, and inline tag/genre editing are all built.

Edits split by how often a field changes: tags, genres and the favourite flag
are inline here; the film's fixed record (titles, year, director, runtime,
poster, Letterboxd link) is edited in `views/film-form/`, which this view's
Edit action opens at `film/:id/edit`.
