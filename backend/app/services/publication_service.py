import json
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import PUBLIC_BASE_URL
from app.models.carrossel import (
    Publicacao,
    STATUS_AGENDADO,
    STATUS_ERRO_PUBLICACAO,
    STATUS_PUBLICADO,
)
from app.services.log_service import registrar_log
from app.services.user_config_service import UserCredentials, credentials_from_config

GRAPH_API_BASE = "https://graph.facebook.com/v20.0"


def _post_graph(path: str, data: dict) -> dict:
    encoded = urlencode(data, doseq=True).encode("utf-8")
    request = Request(f"{GRAPH_API_BASE}/{path.lstrip('/')}", data=encoded, method="POST")
    try:
        with urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise HTTPException(status_code=502, detail=f"Falha na API do Instagram/Facebook: {body}") from exc
    except URLError as exc:
        raise HTTPException(status_code=502, detail=f"Falha ao conectar na API do Instagram/Facebook: {exc.reason}") from exc


def _public_image_url(imagem_url: str | None) -> str | None:
    if not imagem_url:
        return None
    if imagem_url.startswith("https://"):
        return imagem_url
    if imagem_url.startswith("http://"):
        return None
    base = PUBLIC_BASE_URL.rstrip("/")
    if not base.startswith("https://"):
        return None
    return f"{base}{imagem_url if imagem_url.startswith('/') else '/' + imagem_url}"


def _validate_publish(publicacao: Publicacao, credentials: UserCredentials) -> list[str]:
    carrossel = publicacao.carrossel
    missing = []
    if not credentials.instagram_access_token:
        missing.append("INSTAGRAM_ACCESS_TOKEN")
    if not credentials.instagram_user_id:
        missing.append("INSTAGRAM_USER_ID")
    if not credentials.facebook_page_id:
        missing.append("FACEBOOK_PAGE_ID")
    if missing:
        raise HTTPException(status_code=409, detail=f"Configure {', '.join(missing)} antes de publicar.")
    if not PUBLIC_BASE_URL.rstrip("/").startswith("https://"):
        raise HTTPException(status_code=409, detail="Configure PUBLIC_BASE_URL com uma URL HTTPS pública antes de publicar no Instagram.")
    slides = sorted(carrossel.slides or [], key=lambda slide: slide.numero_slide)
    urls = [_public_image_url(slide.imagem_url) for slide in slides]
    if not slides or any(url is None for url in urls):
        raise HTTPException(status_code=409, detail="Renderize todos os slides e exponha as imagens via HTTPS antes de publicar.")
    if len(urls) > 10:
        raise HTTPException(status_code=409, detail="Instagram aceita no máximo 10 imagens em um carrossel.")
    return [url for url in urls if url]


def publicar_real_instagram(db: Session, publicacao: Publicacao, *, credentials: UserCredentials) -> Publicacao:
    carrossel = publicacao.carrossel
    if publicacao.status == STATUS_PUBLICADO:
        return publicacao
    if carrossel.status == STATUS_PUBLICADO:
        publicacao.status = STATUS_ERRO_PUBLICACAO
        publicacao.erro = "Carrossel já publicado."
        return publicacao

    urls = _validate_publish(publicacao, credentials)
    token = credentials.instagram_access_token
    ig_user_id = credentials.instagram_user_id
    caption = carrossel.legenda or carrossel.titulo or ""

    try:
        if len(urls) == 1:
            creation = _post_graph(f"{ig_user_id}/media", {"image_url": urls[0], "caption": caption, "access_token": token})
        else:
            children = []
            for url in urls:
                item = _post_graph(f"{ig_user_id}/media", {"image_url": url, "is_carousel_item": "true", "access_token": token})
                children.append(item["id"])
            creation = _post_graph(
                f"{ig_user_id}/media",
                {"media_type": "CAROUSEL", "children": ",".join(children), "caption": caption, "access_token": token},
            )
        published = _post_graph(f"{ig_user_id}/media_publish", {"creation_id": creation["id"], "access_token": token})
    except HTTPException as exc:
        publicacao.status = STATUS_ERRO_PUBLICACAO
        publicacao.erro = str(exc.detail)
        carrossel.status = STATUS_ERRO_PUBLICACAO
        carrossel.erro_publicacao = publicacao.erro
        registrar_log(db, carrossel_id=carrossel.id, etapa="publicacao", status="ERRO", mensagem="Publicação real falhou.", detalhes={"publicacao_id": publicacao.id, "erro": publicacao.erro})
        raise

    now = datetime.utcnow()
    publicacao.status = STATUS_PUBLICADO
    publicacao.publicado_em = now
    publicacao.external_post_id = published.get("id")
    publicacao.resposta_api = {"creation": creation, "published": published}
    publicacao.erro = None
    carrossel.status = STATUS_PUBLICADO
    carrossel.publicado_em = now
    carrossel.erro_publicacao = None
    registrar_log(db, carrossel_id=carrossel.id, etapa="publicacao", status="CONCLUIDO", mensagem="Publicação real concluída.", detalhes={"publicacao_id": publicacao.id, "external_post_id": publicacao.external_post_id})
    return publicacao


def publicar_agendadas_vencidas(db: Session) -> int:
    vencidas = (
        db.query(Publicacao)
        .filter(Publicacao.status == STATUS_AGENDADO)
        .filter(Publicacao.agendado_para <= datetime.utcnow())
        .all()
    )
    total = 0
    for publicacao in vencidas:
        credentials = credentials_from_config(publicacao.carrossel.usuario.configuracao if publicacao.carrossel and publicacao.carrossel.usuario else None)
        publicar_real_instagram(db, publicacao, credentials=credentials)
        total += 1
    return total
