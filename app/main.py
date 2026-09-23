from fastapi import FastAPI

from app.api.routes import health, projects, specs, test_cases, test_runs
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="OpenAPI test intelligence platform.",
        version="0.1.0",
    )

    app.include_router(health.router, tags=["health"])
    app.include_router(projects.router, prefix="/projects", tags=["projects"])
    app.include_router(specs.router, tags=["specs"])
    app.include_router(test_cases.router, tags=["test-cases"])
    app.include_router(test_runs.router, tags=["test-runs"])
    return app


app = create_app()
