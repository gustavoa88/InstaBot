from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.carrossel import Usuario, UsuarioConfiguracao
from app.security import decrypt_secret, encrypt_secret, mask_secret


@dataclass
class UserCredentials:
    openai_api_key: str | None = None
    instagram_access_token: str | None = None
    instagram_user_id: str | None = None
    facebook_page_id: str | None = None


def get_or_create_config(db: Session, usuario: Usuario) -> UsuarioConfiguracao:
    config = usuario.configuracao
    if config is None:
        config = UsuarioConfiguracao(usuario_id=usuario.id)
        db.add(config)
        db.flush()
    return config


def update_config(db: Session, usuario: Usuario, payload) -> UsuarioConfiguracao:
    config = get_or_create_config(db, usuario)
    data = payload.model_dump(exclude_unset=True)
    field_map = {
        "openai_api_key": "openai_api_key_encrypted",
        "instagram_access_token": "instagram_access_token_encrypted",
        "instagram_user_id": "instagram_user_id_encrypted",
        "facebook_page_id": "facebook_page_id_encrypted",
    }
    for input_name, column_name in field_map.items():
        if input_name in data:
            value = data[input_name]
            setattr(config, column_name, encrypt_secret(value.strip()) if value else None)
    db.flush()
    return config


def credentials_from_config(config: UsuarioConfiguracao | None) -> UserCredentials:
    if config is None:
        return UserCredentials()
    return UserCredentials(
        openai_api_key=decrypt_secret(config.openai_api_key_encrypted),
        instagram_access_token=decrypt_secret(config.instagram_access_token_encrypted),
        instagram_user_id=decrypt_secret(config.instagram_user_id_encrypted),
        facebook_page_id=decrypt_secret(config.facebook_page_id_encrypted),
    )


def credentials_for_user(db: Session, usuario: Usuario) -> UserCredentials:
    db.refresh(usuario)
    return credentials_from_config(usuario.configuracao)


def config_public(config: UsuarioConfiguracao | None) -> dict:
    creds = credentials_from_config(config)
    return {
        "openai_configurado": bool(creds.openai_api_key),
        "instagram_configurado": bool(creds.instagram_access_token and creds.instagram_user_id and creds.facebook_page_id),
        "openai_api_key_masked": mask_secret(creds.openai_api_key),
        "instagram_access_token_masked": mask_secret(creds.instagram_access_token),
        "instagram_user_id_masked": mask_secret(creds.instagram_user_id),
        "facebook_page_id_masked": mask_secret(creds.facebook_page_id),
    }
