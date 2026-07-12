"""Application factory and ASGI entrypoint for the Film Rewatch backend.

Builds the FastAPI app (DESIGN §3.2 — API-first), mounts the versioned
``/api/v1`` router, and wires each feature module's router into it (§5.1).
OpenAPI/Swagger is served by FastAPI at ``/docs`` and ``/openapi.json``.

Run locally with::

    uvicorn app.main:app --reload

CORS is wired below from configuration (PR2), and the single error-envelope
exception handler (PR5) is registered on the app (DESIGN §5.4, NFR-MAINT-03).
"""

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.films.router import router as films_router
from app.genres.router import router as genres_router
from app.ratings.router import router as ratings_router
from app.rewatch.router import router as rewatch_router
from app.tags.router import router as tags_router

API_V1_PREFIX = "/api/v1"


def health() -> dict[str, str]:
    """Liveness probe — a placeholder until M1 adds real routes (DESIGN §10, M0)."""
    return {"status": "ok"}


def build_api_router() -> APIRouter:
    """Assemble the versioned ``/api/v1`` router from each feature module.

    The module routers are empty stubs in M0; including them here establishes
    the §5.1 wiring (a router never imports a repository) so M1 only has to add
    routes inside each module.
    """
    api = APIRouter(prefix=API_V1_PREFIX)
    api.add_api_route("/health", health, methods=["GET"], tags=["health"], summary="Liveness probe")

    api.include_router(films_router, prefix="/films", tags=["films"])
    api.include_router(ratings_router, prefix="/ratings", tags=["ratings"])
    api.include_router(tags_router, prefix="/tags", tags=["tags"])
    api.include_router(genres_router, prefix="/genres", tags=["genres"])
    api.include_router(rewatch_router, prefix="/rewatch-suggestions", tags=["rewatch"])
    # There is no ``app/adapters`` module — the adapter pattern (§5.6) is future
    # work, if ever. Were one built, it would be an internal integration
    # surface, not a public API namespace, so nothing would be mounted here.
    return api


def create_app() -> FastAPI:
    """Application factory: build and configure the FastAPI app (DESIGN §5.1)."""
    settings = get_settings()
    app = FastAPI(
        title="Film Rewatch API",
        # App version (SemVer 2.0.0, policy in the root README). The /api/vN
        # contract is SemVer's "public API": breaking it bumps MAJOR and the
        # URL version together.
        version="0.1.0",
        summary="Backend API for the Film Rewatch application.",
        description=(
            "Versioned (`v1`) HTTP/JSON API. M0 ships only the structural "
            "skeleton and a liveness endpoint; domain endpoints arrive in M1+."
        ),
    )
    # Allowed origins come from config — the backend hardcodes no client origin
    # (DESIGN §3.6/§8). The app has no auth/cookies, so credentials stay off.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Every error response uses the single envelope (NFR-MAINT-03, §5.4); these
    # handlers override FastAPI's defaults so no route can emit another shape.
    register_exception_handlers(app)
    app.include_router(build_api_router())
    return app


app = create_app()
