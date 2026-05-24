from sqlalchemy.orm import Session

from app.models.carrossel import (
    Carrossel,
    CarrosselSlide,
    STATUS_AGUARDANDO_APROVACAO,
    STATUS_GERANDO,
)
from app.services.log_service import registrar_log


def _titulo_curto_da_ideia(ideia: str, limite: int = 90) -> str:
    primeira_linha = (ideia or "").strip().splitlines()[0].strip()
    if not primeira_linha:
        return "Ideia central do carrossel"
    if len(primeira_linha) <= limite:
        return primeira_linha
    corte = primeira_linha[:limite].rsplit(" ", 1)[0].strip() or primeira_linha[:limite].strip()
    return f"{corte}..."


def gerar_carrossel_mockado(db: Session, carrossel: Carrossel, *, regenerar: bool = False) -> Carrossel:
    carrossel.status = STATUS_GERANDO
    registrar_log(
        db,
        carrossel_id=carrossel.id,
        etapa="geracao",
        status="INICIADO",
        mensagem="Geração mockada iniciada.",
        detalhes={"regenerar": regenerar},
    )

    if regenerar:
        for slide in list(carrossel.slides):
            db.delete(slide)
        db.flush()

    quantidade = carrossel.quantidade_slides or 7
    carrossel.titulo = carrossel.titulo or _titulo_curto_da_ideia(carrossel.ideia_original)
    carrossel.tema = carrossel.tema or "tema principal"
    carrossel.publico_alvo = carrossel.publico_alvo or "público geral"
    tema = carrossel.tema
    tom = carrossel.tom or "claro e direto"
    publico = carrossel.publico_alvo

    for numero in range(1, quantidade + 1):
        if numero == 1:
            titulo = carrossel.titulo
            texto = carrossel.ideia_original
            observacao = "Slide de abertura com título forte e visual limpo."
        elif numero == quantidade:
            titulo = "Próximo passo"
            texto = "Salve este conteúdo e aplique uma ação prática ainda hoje."
            observacao = "Slide final com CTA destacado."
        else:
            titulo = f"Ponto {numero - 1}: {tema}"
            texto = f"Explique este ponto em tom {tom}, conectando com {publico}."
            observacao = "Usar fundo conceitual sem texto embutido na imagem."

        db.add(
            CarrosselSlide(
                carrossel_id=carrossel.id,
                numero_slide=numero,
                titulo=titulo,
                texto_principal=texto,
                texto_secundario=None,
                observacao_visual=observacao,
                layout_config={"template": "mvp_default", "mock": True},
            )
        )

    carrossel.legenda = carrossel.legenda or f"{carrossel.titulo}\n\nConteúdo gerado para revisão manual."
    carrossel.hashtags = carrossel.hashtags or ["#conteudo", "#carrossel", "#instagram"]
    carrossel.ia_resultado = {
        "mock": True,
        "quantidade_slides": quantidade,
        "titulo": carrossel.titulo,
        "tema": carrossel.tema,
        "publico_alvo": carrossel.publico_alvo,
        "observacao": "Substituir por OpenAI após validação do fluxo MVP.",
    }
    carrossel.status = STATUS_AGUARDANDO_APROVACAO

    registrar_log(
        db,
        carrossel_id=carrossel.id,
        etapa="geracao",
        status="CONCLUIDO",
        mensagem="Geração mockada concluída.",
        detalhes={"slides_criados": quantidade},
    )
    return carrossel


def gerar_carrossel_textual(db: Session, carrossel: Carrossel, *, regenerar: bool = False) -> Carrossel:
    from app.services.ai_service import gerar_carrossel_com_openai, openai_configurado

    if not openai_configurado():
        registrar_log(
            db,
            carrossel_id=carrossel.id,
            etapa="geracao_ia",
            status="FALLBACK_MOCK",
            mensagem="OPENAI_API_KEY não configurada; usando geração mockada.",
            detalhes={"regenerar": regenerar},
        )
        return gerar_carrossel_mockado(db, carrossel, regenerar=regenerar)

    return gerar_carrossel_com_openai(db, carrossel, regenerar=regenerar)
