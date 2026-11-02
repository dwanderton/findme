from __future__ import annotations

import os
from pathlib import Path

DATACENTER = "US-IL-1"
VOLUME_MOUNT = Path("/runpod-volume")

GPU_WORKERS = (0, 20)
GPU_LB_WORKERS = (0, 2)
CPU_WORKERS = (0, 4)
CPU_LB_WORKERS = (0, 2)
VLM_WORKERS = (0, 2)

IDLE_TIMEOUT_S = 30
EXECUTION_TIMEOUT_MS = 600_000
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
