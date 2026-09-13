# `domain/tag/`

The tag entity module (DESIGN §4/§6.1) — the read-only lookup behind the
FR-TAG-06 autocomplete: `api.ts` fetches `GET /tags` once, `facade.ts` exposes
the names.

Built ahead of its milestone (M3) alongside the Film Detail view's tag
editing, like the rest of that view. There is no `model.ts`/`mapper.ts`: above
the data layer a tag _is_ its name, and tags are written only as part of a
film payload (`FilmFacade.update`), never on their own.
