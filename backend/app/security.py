from hmac import compare_digest

from fastapi import Header, HTTPException, status

from app.config import ADMIN_API_TOKEN


def require_admin_token(x_admin_token: str | None = Header(default=None)) -> None:
    expected = ADMIN_API_TOKEN.strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Token administrativo não configurado.",
        )
    if not x_admin_token or not compare_digest(x_admin_token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token administrativo inválido ou ausente.",
        )
