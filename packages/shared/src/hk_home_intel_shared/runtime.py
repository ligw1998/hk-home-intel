from pathlib import Path

from hk_home_intel_shared.settings import get_settings


RUNTIME_DIRS = [
    "dev",
    "raw",
    "snapshots",
    "documents",
    "images",
    "exports",
]


def ensure_runtime_dirs() -> list[Path]:
    settings = get_settings()
    created = []
    for name in RUNTIME_DIRS:
        path = settings.data_root / name
        path.mkdir(parents=True, exist_ok=True)
        created.append(path)
    return created
