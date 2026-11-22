from __future__ import annotations

import uuid
from typing import Optional
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from gramsetu.core import (
    Settings,
    GramSetuError,
    get_current_utc,
)
from gramsetu.schemas import HealthStatus
from gramsetu.store import InMemoryStore, TransactionCoordinator
from gramsetu.security.identity import get_identity_adapter
from gramsetu.api.v1.router import api_v1_router


def create_app(
    settings: Optional[Settings] = None,
    store: Optional[InMemoryStore] = None,
    coordinator: Optional[TransactionCoordinator] = None,
) -> FastAPI:
    cfg = settings or Settings()

    if coordinator is None:
        if store is None:
            if cfg.SNAPSHOT_PATH:
                store = InMemoryStore.load_from_snapshot(cfg.SNAPSHOT_PATH)
            else:
                store = InMemoryStore()
        coordinator = TransactionCoordinator(store=store, snapshot_path=cfg.SNAPSHOT_PATH)
    else:
        store = coordinator.store

    app = FastAPI(
        title=cfg.APP_NAME,
        version=cfg.APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.state.settings = cfg
    app.state.store = store
    app.state.coordinator = coordinator
    app.state.identity_adapter = get_identity_adapter(cfg)

    # Request Trace ID and path alias middleware
    @app.middleware("http")
    async def trace_and_size_middleware(request: Request, call_next):
        # Support /v1 alias alongside /api/v1
        if request.scope["path"].startswith("/v1/"):
            request.scope["path"] = "/api" + request.scope["path"]
            if "raw_path" in request.scope:
                request.scope["raw_path"] = b"/api" + request.scope["raw_path"]

        trace_id = request.headers.get("X-Trace-Id", str(uuid.uuid4()))
        request.state.trace_id = trace_id

        # Size check
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > cfg.MAX_REQUEST_SIZE_BYTES:
            return JSONResponse(
                status_code=413,
                content={
                    "error": "PAYLOAD_TOO_LARGE",
                    "message": f"Request body exceeds {cfg.MAX_REQUEST_SIZE_BYTES} bytes",
                    "status_code": 413,
                    "trace_id": trace_id,
                },
            )

        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        return response

    # Exception Handlers
    @app.exception_handler(GramSetuError)
    async def gramsetu_error_handler(request: Request, exc: GramSetuError):
        trace_id = getattr(request.state, "trace_id", None)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.error_code,
                "message": exc.message,
                "status_code": exc.status_code,
                "details": exc.details,
                "trace_id": trace_id,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        trace_id = getattr(request.state, "trace_id", None)
        return JSONResponse(
            status_code=422,
            content={
                "error": "UNPROCESSABLE_ENTITY",
                "message": "Validation error in request parameters or body",
                "status_code": 422,
                "details": {"errors": exc.errors()},
                "trace_id": trace_id,
            },
        )

    # Health check endpoint
    @app.get("/health", response_model=HealthStatus)
    async def health_check(request: Request):
        return HealthStatus(
            status="ok",
            version=cfg.APP_VERSION,
            environment=cfg.ENVIRONMENT.value,
            timestamp=get_current_utc(),
            stats=coordinator.store.get_stats(),
        )

    # Mount static assets and UI routes
    import os
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

        assets_dir = os.path.join(static_dir, "assets")
        if os.path.exists(assets_dir):
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/", include_in_schema=False)
        @app.get("/app", include_in_schema=False)
        @app.get("/ui", include_in_schema=False)
        async def serve_ui():
            return FileResponse(os.path.join(static_dir, "index.html"))

    # Mount API v1 router
    app.include_router(api_v1_router)

    # SPA Client-side Route Catch-all (for HTML5 pushState routing)
    if os.path.exists(static_dir):
        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str):
            if full_path.startswith("api/") or full_path in ("docs", "redoc", "openapi.json"):
                return JSONResponse(status_code=404, content={"error": "NOT_FOUND", "message": "Endpoint not found"})
            index_path = os.path.join(static_dir, "index.html")
            if os.path.exists(index_path):
                return FileResponse(index_path)
            return JSONResponse(status_code=404, content={"error": "NOT_FOUND", "message": "UI not found"})

    return app


# Default instance for uvicorn
app = create_app()
