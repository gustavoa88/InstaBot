import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, Header, HTTPException, status
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import ACCESS_TOKEN_EXPIRE_MINUTES, APP_SECRET_KEY
from app.database import get_db
from app.models.carrossel import Usuario

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ADMIN_API_TOKEN = ""


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def create_access_token(usuario: Usuario) -> str:
    now = datetime.utcnow()
    payload = {
        "sub": str(usuario.id),
        "email": usuario.email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp()),
        "nonce": secrets.token_hex(8),
    }
    header = {"alg": "HS256", "typ": "JWT"}
    header_part = _b64url(json.dumps(header, separators=(",", ":")).encode())
    payload_part = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_part}.{payload_part}"
    signature = hmac.new(APP_SECRET_KEY.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url(signature)}"


def decode_access_token(token: str) -> dict:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
        signing_input = f"{header_b64}.{payload_b64}"
        expected = hmac.new(APP_SECRET_KEY.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
        actual = _b64url_decode(signature_b64)
        if not hmac.compare_digest(expected, actual):
            raise ValueError("invalid signature")
        payload = json.loads(_b64url_decode(payload_b64))
        if int(payload.get("exp", 0)) < int(datetime.utcnow().timestamp()):
            raise ValueError("expired token")
        return payload
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão inválida ou expirada.") from exc


def get_current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> Usuario:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticação necessária.")
    payload = decode_access_token(authorization.removeprefix("Bearer ").strip())
    usuario = db.query(Usuario).filter(Usuario.id == int(payload["sub"])).first()
    if usuario is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário não encontrado.")
    return usuario


def _fernet() -> Fernet:
    digest = hashlib.sha256(APP_SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value: str | None) -> str | None:
    if not value:
        return None
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise HTTPException(status_code=500, detail="Falha ao descriptografar configuração do usuário.") from exc


def mask_secret(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}...{value[-4:]}"


def require_admin_token(x_admin_token: str | None = None) -> None:
    expected = ADMIN_API_TOKEN.strip()
    if not expected or not x_admin_token or not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token administrativo inválido ou ausente.")
