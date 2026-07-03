# `domain/` — per-entity business logic + data access (DESIGN §4, §6.1)

Intentional **M0 stub** (PR7). Business logic and data access are organised
**per entity**, mirroring the backend's feature modules: `film/`, `rating/`,
`tag/`, `genre/`. Each module takes the same shape when it lands in **M3**:

- `model.ts` — the canonical domain model (§6.1 "three models")
- `validators.ts` — app-wide entity rules, the client mirror of the backend's Pydantic schemas (§5.4)
- `mapper.ts` — DTO ↔ domain mapping
- `api.ts` — typed backend calls on the shared cache-first engine (data access)
- `facade.ts` — the single API the views call (business logic)

Calls flow downward only: views → facades → api (§6.1). Views never import
`api.ts` directly.
