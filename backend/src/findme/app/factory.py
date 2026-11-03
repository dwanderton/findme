from __future__ import annotations

import os
import threading
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from findme import settings
from findme.errors import ApiError


def create_app(root: Path | None = None) -> FastAPI:
    app = FastAPI(title="findMe", docs_url=None, redoc_url=None)
    app.state.root = root or settings.storage_root()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["content-type", "x-owner-token"],
    )

    @app.exception_handler(ApiError)
    async def api_error_handler(_: Request, exc: ApiError):
        return JSONResponse(status_code=exc.status, content=exc.envelope())

    @app.get("/health")
    @app.get("/ping")
    async def health():
        return {"status": "ok"}

    if os.environ.get("FINDME_INLINE_JOBS", "").lower() == "true":
        from findme.jobs.index_cpu import run_cpu_stage
        from findme.jobs.index_gpu import run_all_batches

        def inline_runner(root: Path, album_id: str) -> dict:
            result = run_cpu_stage(root, album_id)
            threading.Thread(target=run_all_batches, args=(root, album_id), daemon=True).start()
            return result

        app.state.run_index = inline_runner

        if os.environ.get("VLM_BASE_URL"):
            import asyncio

            from findme.jobs.vlm_job import run_vlm_job

            def vlm_runner(root: Path, album_id: str, user_id: str, photo_ids: list) -> None:
                def work():
                    asyncio.run(run_vlm_job(root, album_id, user_id, photo_ids))

                threading.Thread(target=work, daemon=True).start()

            app.state.run_vlm = vlm_runner

    from findme.routes import album, delete, enroll, find, media, places, staticmap, status, upload

    app.include_router(album.router)
    app.include_router(upload.router)
    app.include_router(enroll.router)
    app.include_router(status.router)
    app.include_router(find.router)
    app.include_router(media.router)
    app.include_router(places.router)
    app.include_router(staticmap.router)
    app.include_router(delete.router)
    return app
