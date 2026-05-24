import json
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import (
    OPENAI_API_KEY,
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
    STATUS_AGUARDANDO_APROVACAO,
    STATUS_GERANDO,
)
from app.services.log_service import registrar_log


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


def openai_configurado() -> bool:
    return bool(OPENAI_API_KEY.strip())


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


def _limites_configurados() -> dict[str, int]:
    return {
        "daily_request_limit": OPENAI_DAILY_REQUEST_LIMIT,
        "carrossel_request_limit": OPENAI_CARROSSEL_REQUEST_LIMIT,
        "max_output_tokens": OPENAI_MAX_OUTPUT_TOKENS,
    }


def _contar_chamadas_openai(db: Session, *, carrossel_id: int | None = None, desde: datetime | None = None) -> int:
    query = db.query(LogExecucao).filter(
        LogExecucao.etapa == "geracao_ia",
        LogExecucao.status == OPENAI_CALL_STARTED,
    )
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
) -> None:
    detalhes = {
        "escopo": escopo,
        "limite": limite,
        "chamadas_registradas": chamadas,
        "modelo": OPENAI_MODEL,
        "limites": _limites_configurados(),
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


def _verificar_limites(db: Session, carrossel: Carrossel) -> None:
    if OPENAI_DAILY_REQUEST_LIMIT > 0:
        inicio_dia = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        chamadas_dia = _contar_chamadas_openai(db, desde=inicio_dia)
        if chamadas_dia >= OPENAI_DAILY_REQUEST_LIMIT:
            _bloquear_por_limite(
                db,
                carrossel_id=carrossel.id,
                escopo="diário",
                limite=OPENAI_DAILY_REQUEST_LIMIT,
                chamadas=chamadas_dia,
            )

    if OPENAI_CARROSSEL_REQUEST_LIMIT > 0:
        chamadas_carrossel = _contar_chamadas_openai(db, carrossel_id=carrossel.id)
        if chamadas_carrossel >= OPENAI_CARROSSEL_REQUEST_LIMIT:
            _bloquear_por_limite(
                db,
                carrossel_id=carrossel.id,
                escopo="por carrossel",
                limite=OPENAI_CARROSSEL_REQUEST_LIMIT,
                chamadas=chamadas_carrossel,
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


def gerar_carrossel_com_openai(db: Session, carrossel: Carrossel, *, regenerar: bool = False) -> Carrossel:
    _verificar_limites(db, carrossel)

    carrossel.status = STATUS_GERANDO
    request_config = {
        "modelo": OPENAI_MODEL,
        "regenerar": regenerar,
        "max_output_tokens": OPENAI_MAX_OUTPUT_TOKENS,
        "verbosity": OPENAI_VERBOSITY,
        "reasoning_effort": OPENAI_REASONING_EFFORT,
        "limites": _limites_configurados(),
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

    client = OpenAI(api_key=OPENAI_API_KEY)
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

    resultado = json.loads(response.output_text)
    slides = resultado.get("slides", [])
    quantidade_esperada = carrossel.quantidade_slides or len(slides)
    if len(slides) != quantidade_esperada:
        raise ValueError(f"OpenAI retornou {len(slides)} slides; esperado {quantidade_esperada}.")

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
        "response_id": response.id,
        "usage": usage,
        "request_config": request_config,
        "resultado": resultado,
    }

    for slide in sorted(slides, key=lambda item: item["numero_slide"]):
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
            "response_id": response.id,
            "usage": usage,
            "limites": _limites_configurados(),
        },
    )
    return carrossel
