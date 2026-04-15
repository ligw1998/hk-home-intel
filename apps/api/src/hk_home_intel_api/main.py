from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from hk_home_intel_api.routes.commercial_search_monitors import router as commercial_search_monitors_router
from hk_home_intel_api.routes.activity import router as activity_router
from hk_home_intel_api.routes.developments import router as developments_router
from hk_home_intel_api.routes.health import router as health_router
from hk_home_intel_api.routes.listings import router as listings_router
from hk_home_intel_api.routes.search_presets import router as search_presets_router
from hk_home_intel_api.routes.system import router as system_router
from hk_home_intel_api.routes.watchlist import router as watchlist_router
from hk_home_intel_shared.settings import get_settings
from hk_home_intel_shared.runtime import ensure_runtime_dirs


def create_app() -> FastAPI:
    settings = get_settings()
    ensure_runtime_dirs()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router, prefix=settings.api_v1_prefix)
    app.include_router(activity_router, prefix=settings.api_v1_prefix)
    app.include_router(commercial_search_monitors_router, prefix=settings.api_v1_prefix)
    app.include_router(developments_router, prefix=settings.api_v1_prefix)
    app.include_router(listings_router, prefix=settings.api_v1_prefix)
    app.include_router(search_presets_router, prefix=settings.api_v1_prefix)
    app.include_router(system_router, prefix=settings.api_v1_prefix)
    app.include_router(watchlist_router, prefix=settings.api_v1_prefix)

    @app.get("/")
    def root() -> dict[str, str]:
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "docs_url": "/docs",
        }

    return app


app = create_app()


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "hk_home_intel_api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    run()
