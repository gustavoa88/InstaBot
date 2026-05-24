import json
from typing import Any

from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import OPENAI_API_KEY, OPENAI_MODEL
from app.models.carrossel import Carrossel, CarrosselSlide, STATUS_AGUARDANDO_APROVACAO, STATUS_GERANDO
from app.services.log_service import registrar_log


CARROSSEL_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["titulo", "slides", "legenda", "hashtags", "cta_final"],
    "properties": {
        "titulo": {"type": "string"},
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


def openai_configurado() -> bool:
    return bool(OPENAI_API_KEY.strip())


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

    return f"""
Crie um roteiro de carrossel para Instagram com {carrossel.quantidade_slides or 7} slides.

Dados da ideia:
- Título atual: {carrossel.titulo or "não definido"}
- Ideia original: {carrossel.ideia_original}
- Tema: {carrossel.tema or "não definido"}
- Tom de voz: {carrossel.tom or "claro, útil e direto"}
- Público-alvo: {carrossel.publico_alvo or "público geral"}
- Observações adicionais: {observacoes or "nenhuma"}

Regras:
- Escreva em português do Brasil.
- O primeiro slide deve funcionar como abertura forte.
- O último slide deve ter fechamento e chamada para ação.
- Os textos devem ser curtos o suficiente para caber em slides de Instagram.
- Não inclua texto crítico nas observações visuais; elas são briefing para imagem/renderização futura.
- Retorne exatamente a quantidade de slides solicitada.
""".strip()


def gerar_carrossel_com_openai(db: Session, carrossel: Carrossel, *, regenerar: bool = False) -> Carrossel:
    carrossel.status = STATUS_GERANDO
    registrar_log(
        db,
        carrossel_id=carrossel.id,
        etapa="geracao_ia",
        status="INICIADO",
        mensagem="Geração textual com OpenAI iniciada.",
        detalhes={"modelo": OPENAI_MODEL, "regenerar": regenerar},
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
        text={
            "format": {
                "type": "json_schema",
                "name": "carrossel_textual",
                "strict": True,
                "schema": CARROSSEL_RESPONSE_SCHEMA,
            }
        },
    )

    resultado = json.loads(response.output_text)
    slides = resultado.get("slides", [])
    quantidade_esperada = carrossel.quantidade_slides or len(slides)
    if len(slides) != quantidade_esperada:
        raise ValueError(f"OpenAI retornou {len(slides)} slides; esperado {quantidade_esperada}.")

    carrossel.titulo = resultado["titulo"] or carrossel.titulo
    carrossel.legenda = resultado["legenda"]
    carrossel.hashtags = _normalizar_hashtags(resultado.get("hashtags", []))
    carrossel.ia_resultado = {
        "mock": False,
        "provider": "openai",
        "model": OPENAI_MODEL,
        "response_id": response.id,
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
        detalhes={"modelo": OPENAI_MODEL, "slides_criados": len(slides), "response_id": response.id},
    )
    return carrossel
