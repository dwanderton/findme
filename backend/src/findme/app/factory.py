from __future__ import annotations

import os
import re
import threading
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from findme import settings
from findme.errors import ApiError
from findme.trace import global_writer, writer_for

ALBUM_PATH = re.compile(r"/albums/([0-9a-fA-F-]{8,36})")


def create_app(root: Path | None = None) -> FastAPI:
    app = FastAPI(title="findMe", docs_url=None, redoc_url=None)
    app.state.root = root or settings.storage_root()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["content-type", "x-owner-token"],
    )

    @app.middleware("http")
    async def trace_requests(request: Request, call_next):
        started = time.monotonic()
        response = await call_next(request)
        if not settings.DEBUG_UI:
            return response
        path = request.url.path
        rid = request.headers.get("x-request-id", "")
        # /debug polling would trace itself; health checks are noise unless a
        # request id marks them as user-initiated (the warmup route sends one).
        if path.startswith("/debug") or (path in ("/ping", "/health") and not rid):
            return response
        album_id = request.query_params.get("albumId")
        if not album_id:
            m = ALBUM_PATH.search(path)
            album_id = m.group(1) if m else None
        status = response.status_code
        trace = writer_for(app.state.root, album_id, "api") or global_writer(app.state.root, "api")
        trace.emit(
            "server",
            "http",
            level="error" if status >= 500 else "warn" if status >= 400 else "info",
            request_id=rid,
            method=request.method,
            path=path,
            status=status,
            ms=round((time.monotonic() - started) * 1000),
        )
        return response

    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError):
        rid = request.headers.get("x-request-id", "")
        if rid:
            exc.request_id = rid
        album_id = request.path_params.get("album_id") or request.query_params.get("albumId")
        trace = writer_for(request.app.state.root, album_id, "api")
        if trace:
            trace.emit(
                "api",
                f"error.{exc.code}",
                level="error" if exc.status >= 500 else "warn",
                request_id=exc.request_id,
                status=exc.status,
                path=request.url.path,
            )
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

            from findme.jobs.vlm_job import make_vlm_runner, run_vlm_job

            def spawn(root: Path, album_id: str, user_id: str, photo_ids: list, release) -> None:
                def work():
                    try:
                        asyncio.run(run_vlm_job(root, album_id, user_id, photo_ids))
                    finally:
                        release()

                threading.Thread(target=work, daemon=True).start()

            app.state.run_vlm = make_vlm_runner(spawn)

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
