from fastapi import APIRouter
from app.schemas.carrossel import CarrosselCreate

router = APIRouter()


@router.post("/carrosseis")
def criar_carrossel(payload: CarrosselCreate):
    return {
        "message": "carrossel criado",
        "data": payload
    }
