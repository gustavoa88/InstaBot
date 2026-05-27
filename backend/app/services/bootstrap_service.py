from sqlalchemy.orm import Session

from app.config import BOOTSTRAP_ADMIN_EMAIL, BOOTSTRAP_ADMIN_PASSWORD
from app.models.carrossel import Carrossel, Usuario
from app.security import hash_password

BOOTSTRAP_HASH_MARKER = "bootstrap-password-not-initialized"


def bootstrap_admin(db: Session) -> Usuario:
    email = BOOTSTRAP_ADMIN_EMAIL.strip().lower()
    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    placeholder = db.query(Usuario).filter(Usuario.senha_hash == BOOTSTRAP_HASH_MARKER).first()
    if usuario is None and placeholder is not None:
        usuario = placeholder
        usuario.email = email
        usuario.nome = usuario.nome or "Admin"
    if usuario is None:
        usuario = Usuario(
            email=email,
            nome="Admin",
            senha_hash=hash_password(BOOTSTRAP_ADMIN_PASSWORD),
            is_admin=True,
        )
        db.add(usuario)
        db.flush()
    elif usuario.senha_hash == BOOTSTRAP_HASH_MARKER:
        usuario.senha_hash = hash_password(BOOTSTRAP_ADMIN_PASSWORD)
        usuario.is_admin = True

    db.query(Carrossel).filter(Carrossel.usuario_id.is_(None)).update({Carrossel.usuario_id: usuario.id})
    db.commit()
    db.refresh(usuario)
    return usuario
