from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.config import APP_ENV, STORAGE_PATH
from app.database import engine
from app.routes.carrossel import router as carrossel_router

app = FastAPI(
    title="Content Carousel Automation Platform",
    version="0.1.0"
)

app.include_router(carrossel_router)

Path(STORAGE_PATH).mkdir(parents=True, exist_ok=True)
app.mount("/storage", StaticFiles(directory=STORAGE_PATH), name="storage")

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "content-carousel-backend"
    }

@app.get("/health/db")
def db_health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "database": "connected"
        }

    except Exception as exc:
        response = {"database": "error"}
        if APP_ENV == "development":
            response["detail"] = exc.__class__.__name__
        return response