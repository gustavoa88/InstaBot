from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.carrossel import Usuario
from app.schemas.carrossel import ConfiguracaoRead, ConfiguracaoUpdate
from app.security import get_current_user
from app.services.user_config_service import config_public, get_or_create_config, update_config

router = APIRouter(prefix="/configuracoes", tags=["configuracoes"])


@router.get("", response_model=ConfiguracaoRead)
def obter_configuracoes(usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    config = get_or_create_config(db, usuario)
    db.commit()
    return config_public(config)


@router.put("", response_model=ConfiguracaoRead)
def salvar_configuracoes(payload: ConfiguracaoUpdate, usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    config = update_config(db, usuario, payload)
    db.commit()
    db.refresh(config)
    return config_public(config)
