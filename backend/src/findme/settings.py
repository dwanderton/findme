from __future__ import annotations

import os
from pathlib import Path

VOLUME_MOUNT = Path("/runpod-volume")

BATCH_SIZE = 50

MAX_PHOTOS = int(os.environ.get("MAX_PHOTOS", "5000"))
DEBUG_UI = os.environ.get("DEBUG_UI", "true").lower() == "true"
ZIP_PART_LIMIT = 25 * 1024 * 1024

CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]


def storage_root() -> Path:
    override = os.environ.get("FINDME_STORAGE_ROOT")
    if override:
        return Path(override)
    return VOLUME_MOUNT
