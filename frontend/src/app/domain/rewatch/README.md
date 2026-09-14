# `domain/rewatch/` — the due-list

Data access and business logic for the rewatch suggestions (DESIGN §6.3).

The algorithm runs on the backend (§5.8); this layer only consumes its result.
The wire shape is bare `film_id` + `days_until_next_rewatch`, so `facade.ts`
joins each entry to the cached film metadata from `domain/film/` to produce the
cards `views/rewatch/` renders — in the algorithm's order, never re-sorted
(FR-RW-04).

`removeFilm` is the one client-side rule here: a film the user has just watched
leaves the list immediately rather than waiting for tomorrow's run.
