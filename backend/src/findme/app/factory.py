from __future__ import annotations

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
    async def health():
        return {"status": "ok"}

    from findme.routes import delete, enroll, find, media, status, upload

    app.include_router(upload.router)
    app.include_router(enroll.router)
    app.include_router(status.router)
    app.include_router(find.router)
    app.include_router(media.router)
    app.include_router(delete.router)
    return app
