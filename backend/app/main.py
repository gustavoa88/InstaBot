from fastapi import FastAPI
from sqlalchemy import text

from app.database import engine
from app.routes.carrossel import router as carrossel_router

app = FastAPI(
    title="Content Carousel Automation Platform",
    version="0.1.0"
)

app.include_router(carrossel_router)

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

    except Exception as e:
        return {
            "database": "error",
            "detail": str(e)
        }