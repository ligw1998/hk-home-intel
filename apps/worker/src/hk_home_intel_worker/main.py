import json

from hk_home_intel_shared.runtime import ensure_runtime_dirs
from hk_home_intel_shared.settings import get_settings


def main() -> None:
    settings = get_settings()
    ensure_runtime_dirs()

    summary = {
        "worker": "hk-home-intel",
        "status": "ready",
        "environment": settings.environment,
        "database_url": settings.database_url,
        "data_root": str(settings.data_root),
        "next_step": "Implement schedulers and source adapters in Phase 1.",
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
