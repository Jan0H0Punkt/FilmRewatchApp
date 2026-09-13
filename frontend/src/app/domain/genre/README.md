# `domain/genre/`

The genre entity module (DESIGN §4/§6.1) — the read-only lookup behind the
genre autocomplete: `api.ts` fetches `GET /genres` once, `facade.ts` exposes
the names. Genres are modelled exactly as tags are (REQ §4.4), so this module
mirrors `../tag/` file for file, including the absence of a `model.ts`.

Built ahead of its milestone (M3) alongside the Film Detail view's genre
editing.
