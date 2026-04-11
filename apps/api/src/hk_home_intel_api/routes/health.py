from fastapi import APIRouter

from hk_home_intel_shared.db import database_health
from hk_home_intel_shared.settings import get_settings

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict[str, object]:
    settings = get_settings()
    db_health = database_health(settings.database_url)

    return {
        "status": "ok",
        "environment": settings.environment,
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "api_prefix": settings.api_v1_prefix,
        "database": db_health,
    }
