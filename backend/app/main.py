"""Application factory and ASGI entrypoint for the Film Rewatch backend.

Builds the FastAPI app (DESIGN §3.2 — API-first), mounts the versioned
``/api/v1`` router, and wires each feature module's router into it (§5.1).
OpenAPI/Swagger is served by FastAPI at ``/docs`` and ``/openapi.json``.

Run locally with::

    uvicorn app.main:app --reload

Later M0 PRs attach to this factory at the marked points: CORS middleware (PR2)
and the error-envelope exception handler (PR5).
"""

from fastapi import APIRouter, FastAPI

from app.films.router import router as films_router
from app.genres.router import router as genres_router
from app.ratings.router import router as ratings_router
from app.rewatch.router import router as rewatch_router
from app.tags.router import router as tags_router

API_V1_PREFIX = "/api/v1"


def build_api_router() -> APIRouter:
    """Assemble the versioned ``/api/v1`` router from each feature module.

    The module routers are empty stubs in M0; including them here establishes
    the §5.1 wiring (a router never imports a repository) so M1 only has to add
    routes inside each module.
    """
    api = APIRouter(prefix=API_V1_PREFIX)

    @api.get("/health", tags=["health"], summary="Liveness probe")
    def health() -> dict[str, str]:
        """Liveness placeholder until M1 (DESIGN §10, M0)."""
        return {"status": "ok"}

    api.include_router(films_router, prefix="/films", tags=["films"])
    api.include_router(ratings_router, prefix="/ratings", tags=["ratings"])
    api.include_router(tags_router, prefix="/tags", tags=["tags"])
    api.include_router(genres_router, prefix="/genres", tags=["genres"])
    api.include_router(
        rewatch_router, prefix="/rewatch-suggestions", tags=["rewatch"]
    )
    # ``app/adapters`` is an internal integration surface (§5.6), not a public
    # API namespace, so it is intentionally not mounted here.
    return api


def create_app() -> FastAPI:
    """Application factory: build and configure the FastAPI app (DESIGN §5.1)."""
    app = FastAPI(
        title="Film Rewatch API",
        version="1.0.0",
        summary="Backend API for the Film Rewatch application.",
        description=(
            "Versioned (`v1`) HTTP/JSON API. M0 ships only the structural "
            "skeleton and a liveness endpoint; domain endpoints arrive in M1+."
        ),
    )
    # CORS middleware (PR2) and the error-envelope handler (PR5) register here.
    app.include_router(build_api_router())
    return app


app = create_app()
