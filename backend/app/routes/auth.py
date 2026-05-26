from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.carrossel import Usuario
from app.schemas.carrossel import TokenRead, UsuarioLogin, UsuarioRead, UsuarioRegister
from app.security import create_access_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _normalize_email(email: str) -> str:
    return email.strip().lower()


@router.post("/register", response_model=TokenRead, status_code=status.HTTP_201_CREATED)
def register(payload: UsuarioRegister, db: Session = Depends(get_db)):
    email = _normalize_email(payload.email)
    existing = db.query(Usuario).filter(Usuario.email == email).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Email já cadastrado.")
    usuario = Usuario(
        email=email,
        nome=payload.nome.strip(),
        senha_hash=hash_password(payload.password),
        is_admin=False,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return {"access_token": create_access_token(usuario), "usuario": usuario}


@router.post("/login", response_model=TokenRead)
def login(payload: UsuarioLogin, db: Session = Depends(get_db)):
    email = _normalize_email(payload.email)
    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if usuario is None or not verify_password(payload.password, usuario.senha_hash):
        raise HTTPException(status_code=401, detail="Email ou senha inválidos.")
    return {"access_token": create_access_token(usuario), "usuario": usuario}


@router.get("/me", response_model=UsuarioRead)
def me(usuario: Usuario = Depends(get_current_user)):
    return usuario
