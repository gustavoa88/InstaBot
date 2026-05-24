from sqlalchemy.orm import Session

from app.models.carrossel import (
    Carrossel,
    CarrosselSlide,
    STATUS_AGUARDANDO_APROVACAO,
    STATUS_GERANDO,
)
from app.services.log_service import registrar_log


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
    tema = carrossel.tema or "tema principal"
    tom = carrossel.tom or "claro e direto"
    publico = carrossel.publico_alvo or "público geral"

    for numero in range(1, quantidade + 1):
        if numero == 1:
            titulo = carrossel.titulo or "Ideia central do carrossel"
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

    carrossel.legenda = carrossel.legenda or f"{carrossel.titulo or tema}\n\nConteúdo gerado para revisão manual."
    carrossel.hashtags = carrossel.hashtags or ["#conteudo", "#carrossel", "#instagram"]
    carrossel.ia_resultado = {
        "mock": True,
        "quantidade_slides": quantidade,
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
