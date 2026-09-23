from __future__ import annotations

from fastapi import FastAPI

from parse_pipeline import __version__
from parse_pipeline.api.routes.jobs import router as jobs_router


def create_app() -> FastAPI:
    app = FastAPI(title="parse-pipeline", version=__version__)
    app.include_router(jobs_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "parse-pipeline", "version": __version__}

    return app


app = create_app()
