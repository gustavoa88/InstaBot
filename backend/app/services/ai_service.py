import json
import re
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import (
    OPENAI_ADMIN_DAILY_REQUEST_LIMIT,
    OPENAI_CARROSSEL_REQUEST_LIMIT,
    OPENAI_DAILY_REQUEST_LIMIT,
    OPENAI_MAX_OUTPUT_TOKENS,
    OPENAI_MODEL,
    OPENAI_REASONING_EFFORT,
    OPENAI_VERBOSITY,
)
from app.models.carrossel import (
    Carrossel,
    CarrosselSlide,
    LogExecucao,
    Usuario,
    STATUS_AGUARDANDO_APROVACAO,
    STATUS_GERANDO,
)
from app.services.log_service import registrar_log

OPENAI_API_KEY = ""


CARROSSEL_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["titulo", "tema", "publico_alvo", "slides", "legenda", "hashtags", "cta_final"],
    "properties": {
        "titulo": {"type": "string"},
        "tema": {"type": "string"},
        "publico_alvo": {"type": "string"},
        "slides": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "numero_slide",
                    "titulo",
                    "texto_principal",
                    "texto_secundario",
                    "observacao_visual",
                ],
                "properties": {
                    "numero_slide": {"type": "integer"},
                    "titulo": {"type": "string"},
                    "texto_principal": {"type": "string"},
                    "texto_secundario": {"type": ["string", "null"]},
                    "observacao_visual": {"type": "string"},
                },
            },
        },
        "legenda": {"type": "string"},
        "hashtags": {
            "type": "array",
            "items": {"type": "string"},
        },
        "cta_final": {"type": "string"},
    },
}

OPENAI_CALL_STARTED = "INICIADO"
OPENAI_LIMIT_BLOCKED = "BLOQUEADO_LIMITE"
PROMPT_FIELD_LIMITS = {
    "titulo": 180,
    "ideia_original": 1200,
    "tema": 180,
    "tom": 120,
    "publico_alvo": 180,
    "observacoes_adicionais": 700,
}


def openai_configurado(api_key: str | None = None) -> bool:
    return bool((api_key if api_key is not None else OPENAI_API_KEY).strip())


def _limitar_texto(valor: str | None, limite: int) -> str:
    texto = (valor or "").strip()
    if len(texto) <= limite:
        return texto
    return f"{texto[:limite].rstrip()}..."


def _limpar_slides(db: Session, carrossel: Carrossel) -> None:
    for slide in list(carrossel.slides):
        db.delete(slide)
    db.flush()


def _normalizar_hashtags(hashtags: list[str]) -> list[str]:
    normalizadas = []
    for hashtag in hashtags:
        texto = hashtag.strip()
        if not texto:
            continue
        if not texto.startswith("#"):
            texto = f"#{texto}"
        normalizadas.append(texto.replace(" ", ""))
    return normalizadas[:20]


def _prompt_usuario(carrossel: Carrossel) -> str:
    observacoes = ""
    if carrossel.prompt_config and carrossel.prompt_config.get("observacoes_adicionais"):
        observacoes = str(carrossel.prompt_config["observacoes_adicionais"])

    titulo = _limitar_texto(carrossel.titulo, PROMPT_FIELD_LIMITS["titulo"]) or "não definido"
    ideia = _limitar_texto(carrossel.ideia_original, PROMPT_FIELD_LIMITS["ideia_original"])
    tema = _limitar_texto(carrossel.tema, PROMPT_FIELD_LIMITS["tema"]) or "não definido"
    tom = _limitar_texto(carrossel.tom, PROMPT_FIELD_LIMITS["tom"]) or "claro, útil e direto"
    publico = _limitar_texto(carrossel.publico_alvo, PROMPT_FIELD_LIMITS["publico_alvo"]) or "público geral"
    observacoes = _limitar_texto(observacoes, PROMPT_FIELD_LIMITS["observacoes_adicionais"]) or "nenhuma"

    return f"""
Crie um roteiro de carrossel para Instagram com {carrossel.quantidade_slides or 7} slides.

Dados da ideia:
- Título atual: {titulo}
- Ideia original: {ideia}
- Tema atual: {tema}
- Tom de voz: {tom}
- Público-alvo atual: {publico}
- Observações adicionais: {observacoes}

Regras:
- Escreva em português do Brasil.
- Sempre retorne um título, um tema e um público-alvo coerentes com a ideia; refine valores existentes quando fizer sentido.
- O título deve ser claro e atrativo, com no máximo 90 caracteres.
- O tema deve ser uma categoria curta.
- O público-alvo deve ser específico o bastante para orientar o conteúdo.
- O primeiro slide deve funcionar como abertura forte.
- O último slide deve ter fechamento e chamada para ação.
- Os textos devem ser curtos o suficiente para caber em slides de Instagram.
- Não inclua texto crítico nas observações visuais; elas são briefing para imagem/renderização futura.
- Retorne exatamente a quantidade de slides solicitada.
""".strip()


def _usuario_is_admin(usuario: Usuario | None, carrossel: Carrossel | None = None) -> bool:
    if usuario is not None:
        return bool(getattr(usuario, "is_admin", False))
    dono = getattr(carrossel, "usuario", None) if carrossel is not None else None
    return bool(getattr(dono, "is_admin", False))


def _limites_configurados(*, usuario: Usuario | None = None, carrossel: Carrossel | None = None) -> dict[str, int]:
    daily_limit = OPENAI_ADMIN_DAILY_REQUEST_LIMIT if _usuario_is_admin(usuario, carrossel) else OPENAI_DAILY_REQUEST_LIMIT
    return {
        "daily_request_limit": daily_limit,
        "carrossel_request_limit": OPENAI_CARROSSEL_REQUEST_LIMIT,
        "max_output_tokens": OPENAI_MAX_OUTPUT_TOKENS,
    }


def _contar_chamadas_openai(
    db: Session,
    *,
    carrossel_id: int | None = None,
    usuario_id: int | None = None,
    desde: datetime | None = None,
) -> int:
    query = db.query(LogExecucao).filter(
        LogExecucao.etapa == "geracao_ia",
        LogExecucao.status == OPENAI_CALL_STARTED,
    )
    if usuario_id is not None:
        query = query.join(Carrossel, LogExecucao.carrossel_id == Carrossel.id).filter(Carrossel.usuario_id == usuario_id)
    if carrossel_id is not None:
        query = query.filter(LogExecucao.carrossel_id == carrossel_id)
    if desde is not None:
        query = query.filter(LogExecucao.created_at >= desde)
    return query.count()


def _bloquear_por_limite(
    db: Session,
    *,
    carrossel_id: int,
    escopo: str,
    limite: int,
    chamadas: int,
    usuario: Usuario | None = None,
    carrossel: Carrossel | None = None,
) -> None:
    detalhes = {
        "escopo": escopo,
        "limite": limite,
        "chamadas_registradas": chamadas,
        "modelo": OPENAI_MODEL,
        "limites": _limites_configurados(usuario=usuario, carrossel=carrossel),
        "usuario_id": getattr(usuario, "id", None),
        "admin": _usuario_is_admin(usuario, carrossel),
    }
    registrar_log(
        db,
        carrossel_id=carrossel_id,
        etapa="geracao_ia",
        status=OPENAI_LIMIT_BLOCKED,
        mensagem=f"Geração com OpenAI bloqueada pelo limite {escopo}.",
        detalhes=detalhes,
    )
    db.commit()
    raise HTTPException(
        status_code=429,
        detail=f"Limite {escopo} de geração com OpenAI atingido ({chamadas}/{limite}).",
    )


def _verificar_limites(db: Session, carrossel: Carrossel, *, usuario: Usuario | None = None) -> None:
    limites = _limites_configurados(usuario=usuario, carrossel=carrossel)
    usuario_id = getattr(usuario, "id", None) or getattr(carrossel, "usuario_id", None)
    daily_limit = limites["daily_request_limit"]
    if daily_limit > 0:
        inicio_dia = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        chamadas_dia = _contar_chamadas_openai(db, usuario_id=usuario_id, desde=inicio_dia)
        if chamadas_dia >= daily_limit:
            _bloquear_por_limite(
                db,
                carrossel_id=carrossel.id,
                escopo="diário",
                limite=daily_limit,
                chamadas=chamadas_dia,
                usuario=usuario,
                carrossel=carrossel,
            )

    carrossel_limit = limites["carrossel_request_limit"]
    if carrossel_limit > 0:
        chamadas_carrossel = _contar_chamadas_openai(db, carrossel_id=carrossel.id)
        if chamadas_carrossel >= carrossel_limit:
            _bloquear_por_limite(
                db,
                carrossel_id=carrossel.id,
                escopo="por carrossel",
                limite=carrossel_limit,
                chamadas=chamadas_carrossel,
                usuario=usuario,
                carrossel=carrossel,
            )


def _usage_to_dict(response: Any) -> dict[str, int | None]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {"input_tokens": None, "output_tokens": None, "total_tokens": None}
    if hasattr(usage, "model_dump"):
        usage_data = usage.model_dump()
    elif isinstance(usage, dict):
        usage_data = usage
    else:
        usage_data = {
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
        }
    return {
        "input_tokens": usage_data.get("input_tokens"),
        "output_tokens": usage_data.get("output_tokens"),
        "total_tokens": usage_data.get("total_tokens"),
    }


def _redact_secret(value: str) -> str:
    return re.sub(r"sk-[A-Za-z0-9_\-]+", "sk-***", value)


def _openai_status_code(exc: Exception) -> int | None:
    status = getattr(exc, "status_code", None)
    if status is not None:
        return int(status)
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    return int(status) if status is not None else None


def _openai_raw_error(exc: Exception) -> str:
    body = getattr(exc, "body", None)
    if body:
        return _redact_secret(str(body))
    response = getattr(exc, "response", None)
    text = getattr(response, "text", None)
    if text:
        return _redact_secret(str(text))
    return _redact_secret(str(exc))


def _openai_generation_error_message(exc: Exception) -> str:
    status_code = _openai_status_code(exc)
    raw_error = _openai_raw_error(exc)
    if status_code == 401:
        return f"Chave OpenAI inválida ou expirada. Atualize OPENAI_API_KEY. Detalhe OpenAI: {raw_error}"
    if status_code == 429:
        return f"Limite de geração textual da OpenAI atingido. Detalhe OpenAI: {raw_error}"
    if status_code is not None:
        return f"Falha na OpenAI ao gerar slides (status {status_code}). Detalhe OpenAI: {raw_error}"
    return f"Falha na OpenAI ao gerar slides. Detalhe OpenAI: {raw_error}"


def _raise_openai_generation_error(db: Session, carrossel: Carrossel, exc: Exception) -> None:
    status_code = _openai_status_code(exc) or 502
    message = _openai_generation_error_message(exc)
    registrar_log(
        db,
        carrossel_id=carrossel.id,
        etapa="geracao_ia",
        status="ERRO_OPENAI",
        mensagem=message,
        detalhes={"status_code": status_code, "modelo": OPENAI_MODEL},
    )
    raise HTTPException(status_code=status_code, detail=message)


def _response_output_text(response: Any) -> str:
    output_text = (getattr(response, "output_text", "") or "").strip()
    if not output_text:
        raise ValueError("OpenAI não retornou output_text.")
    return output_text


def _carregar_resultado_response(response: Any) -> dict[str, Any]:
    try:
        resultado = json.loads(_response_output_text(response))
    except json.JSONDecodeError as exc:
        raise ValueError("OpenAI retornou JSON inválido.") from exc
    if not isinstance(resultado, dict):
        raise ValueError("OpenAI retornou payload em formato inválido.")
    return resultado


def _validar_slides_openai(slides: Any, quantidade_esperada: int) -> list[dict[str, Any]]:
    if not isinstance(slides, list):
        raise ValueError("OpenAI retornou slides em formato inválido.")
    if len(slides) != quantidade_esperada:
        raise ValueError(f"OpenAI retornou {len(slides)} slides; esperado {quantidade_esperada}.")

    numeros = [slide.get("numero_slide") for slide in slides if isinstance(slide, dict)]
    numeros_esperados = list(range(1, quantidade_esperada + 1))
    if sorted(numeros) != numeros_esperados:
        raise ValueError(
            f"OpenAI retornou numeração de slides inválida; esperado {numeros_esperados}."
        )
    return sorted(slides, key=lambda item: item["numero_slide"])


def gerar_carrossel_com_openai(db: Session, carrossel: Carrossel, *, api_key: str | None = None, regenerar: bool = False, usuario: Usuario | None = None) -> Carrossel:
    _verificar_limites(db, carrossel, usuario=usuario)

    carrossel.status = STATUS_GERANDO
    request_config = {
        "modelo": OPENAI_MODEL,
        "regenerar": regenerar,
        "max_output_tokens": OPENAI_MAX_OUTPUT_TOKENS,
        "verbosity": OPENAI_VERBOSITY,
        "reasoning_effort": OPENAI_REASONING_EFFORT,
        "limites": _limites_configurados(usuario=usuario, carrossel=carrossel),
    }
    registrar_log(
        db,
        carrossel_id=carrossel.id,
        etapa="geracao_ia",
        status=OPENAI_CALL_STARTED,
        mensagem="Geração textual com OpenAI iniciada.",
        detalhes=request_config,
    )

    if regenerar or carrossel.slides:
        _limpar_slides(db, carrossel)

    try:
        client = OpenAI(api_key=api_key if api_key is not None else OPENAI_API_KEY)
        try:
            response = client.responses.create(
                model=OPENAI_MODEL,
                instructions=(
                    "Você é um estrategista de conteúdo para Instagram. "
                    "Gere roteiros de carrossel claros, revisáveis e prontos para aprovação humana. "
                    "Use linguagem natural, objetiva e adequada ao público informado."
                ),
                input=_prompt_usuario(carrossel),
                max_output_tokens=OPENAI_MAX_OUTPUT_TOKENS,
                reasoning={"effort": OPENAI_REASONING_EFFORT},
                text={
                    "verbosity": OPENAI_VERBOSITY,
                    "format": {
                        "type": "json_schema",
                        "name": "carrossel_textual",
                        "strict": True,
                        "schema": CARROSSEL_RESPONSE_SCHEMA,
                    },
                },
            )
        except Exception as exc:
            _raise_openai_generation_error(db, carrossel, exc)

        resultado = _carregar_resultado_response(response)
        quantidade_esperada = carrossel.quantidade_slides or 7
        slides = _validar_slides_openai(resultado.get("slides"), quantidade_esperada)
        usage = _usage_to_dict(response)

        carrossel.titulo = resultado["titulo"] or carrossel.titulo
        carrossel.tema = resultado["tema"] or carrossel.tema
        carrossel.publico_alvo = resultado["publico_alvo"] or carrossel.publico_alvo
        carrossel.legenda = resultado["legenda"]
        carrossel.hashtags = _normalizar_hashtags(resultado.get("hashtags", []))
        carrossel.ia_resultado = {
            "mock": False,
            "provider": "openai",
            "model": OPENAI_MODEL,
            "response_id": getattr(response, "id", None),
            "usage": usage,
            "request_config": request_config,
            "resultado": resultado,
        }

        for slide in slides:
            db.add(
                CarrosselSlide(
                    carrossel_id=carrossel.id,
                    numero_slide=slide["numero_slide"],
                    titulo=slide["titulo"],
                    texto_principal=slide["texto_principal"],
                    texto_secundario=slide.get("texto_secundario"),
                    observacao_visual=slide["observacao_visual"],
                    layout_config={"template": "mvp_default", "mock": False, "source": "openai"},
                )
            )
        db.flush()

        carrossel.status = STATUS_AGUARDANDO_APROVACAO
        registrar_log(
            db,
            carrossel_id=carrossel.id,
            etapa="geracao_ia",
            status="CONCLUIDO",
            mensagem="Geração textual com OpenAI concluída.",
            detalhes={
                "modelo": OPENAI_MODEL,
                "slides_criados": len(slides),
                "response_id": getattr(response, "id", None),
                "usage": usage,
                "limites": _limites_configurados(usuario=usuario, carrossel=carrossel),
            },
        )
        return carrossel
    except Exception as exc:
        registrar_log(
            db,
            carrossel_id=carrossel.id,
            etapa="geracao_ia",
            status="ERRO",
            mensagem="Geração textual com OpenAI falhou.",
            detalhes={
                "modelo": OPENAI_MODEL,
                "erro": str(exc),
                "limites": _limites_configurados(usuario=usuario, carrossel=carrossel),
            },
        )
        raise
