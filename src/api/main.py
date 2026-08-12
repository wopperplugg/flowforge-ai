from fastapi import FastAPI

from src.api.v1.assistant import router as assistant_router
from src.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        debug=settings.app_debug,
    )

    app.include_router(
        assistant_router,
        prefix="/v1",
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
        }

    return app


app = create_app()
