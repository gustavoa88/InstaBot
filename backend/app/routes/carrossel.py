from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.carrossel import (
    ASSET_STATUS_ATIVO,
    Carrossel,
    CarrosselAsset,
    CarrosselSlide,
    LogExecucao,
    Publicacao,
    STATUS_AGENDADO,
    STATUS_AGUARDANDO_APROVACAO,
    STATUS_APROVADO,
    STATUS_CANCELADO,
    STATUS_PUBLICADO,
    STATUS_REJEITADO,
)
from app.schemas.carrossel import (
    AgendamentoCreate,
    AssetVisualRead,
    CarrosselCreate,
    CarrosselRead,
    CarrosselUpdate,
    LogExecucaoRead,
    PublicacaoRead,
    ReagendamentoUpdate,
    RenderizacaoCreate,
    SlideRead,
    SlideUpdate,
)
from app.services.generation_service import gerar_carrossel_textual
from app.services.image_asset_service import gerar_asset_visual, remover_asset_visual
from app.services.log_service import registrar_log
from app.services.publication_service import publicar_mockado
from app.security import require_admin_token
from app.services.render_service import renderizar_carrossel_slides

router = APIRouter(dependencies=[Depends(require_admin_token)])


def buscar_carrossel(db: Session, carrossel_id: int) -> Carrossel:
    carrossel = (
        db.query(Carrossel)
        .options(joinedload(Carrossel.slides), joinedload(Carrossel.publicacoes), joinedload(Carrossel.assets))
        .filter(Carrossel.id == carrossel_id)
        .first()
    )
    if carrossel is None:
        raise HTTPException(status_code=404, detail="Carrossel não encontrado.")
    return carrossel


def buscar_publicacao(db: Session, publicacao_id: int) -> Publicacao:
    publicacao = db.query(Publicacao).filter(Publicacao.id == publicacao_id).first()
    if publicacao is None:
        raise HTTPException(status_code=404, detail="Publicação não encontrada.")
    return publicacao


def buscar_asset(db: Session, asset_id: int) -> CarrosselAsset:
    asset = db.query(CarrosselAsset).filter(CarrosselAsset.id == asset_id).first()
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset visual não encontrado.")
    return asset


@router.post("/carrosseis", response_model=CarrosselRead, status_code=status.HTTP_201_CREATED)
def criar_carrossel(payload: CarrosselCreate, db: Session = Depends(get_db)):
    dados = payload.model_dump(exclude={"observacoes_adicionais"})
    carrossel = Carrossel(
        **dados,
        prompt_config={"observacoes_adicionais": payload.observacoes_adicionais}
        if payload.observacoes_adicionais
        else None,
    )
    db.add(carrossel)
    db.flush()
    registrar_log(
        db,
        carrossel_id=carrossel.id,
        etapa="ideia",
        status="CRIADO",
        mensagem="Ideia de carrossel cadastrada.",
    )
    db.commit()
    db.refresh(carrossel)
    return carrossel


@router.get("/carrosseis", response_model=list[CarrosselRead])
def listar_carrosseis(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return (
        db.query(Carrossel)
        .options(joinedload(Carrossel.slides), joinedload(Carrossel.publicacoes), joinedload(Carrossel.assets))
        .order_by(Carrossel.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/carrosseis/{carrossel_id}", response_model=CarrosselRead)
def obter_carrossel(carrossel_id: int, db: Session = Depends(get_db)):
    return buscar_carrossel(db, carrossel_id)


@router.put("/carrosseis/{carrossel_id}", response_model=CarrosselRead)
def atualizar_carrossel(
    carrossel_id: int,
    payload: CarrosselUpdate,
    db: Session = Depends(get_db),
):
    carrossel = buscar_carrossel(db, carrossel_id)
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(carrossel, campo, valor)
    registrar_log(
        db,
        carrossel_id=carrossel.id,
        etapa="ideia",
        status="ATUALIZADO",
        mensagem="Carrossel atualizado.",
        detalhes=payload.model_dump(exclude_unset=True),
    )
    db.commit()
    db.refresh(carrossel)
    return carrossel


@router.delete("/carrosseis/{carrossel_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_carrossel(carrossel_id: int, db: Session = Depends(get_db)):
    carrossel = buscar_carrossel(db, carrossel_id)
    db.delete(carrossel)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/carrosseis/{carrossel_id}/gerar", response_model=CarrosselRead)
def gerar_carrossel(carrossel_id: int, db: Session = Depends(get_db)):
    carrossel = buscar_carrossel(db, carrossel_id)
    if carrossel.slides:
        raise HTTPException(
            status_code=409,
            detail="Carrossel já possui slides. Use /regenerar para substituir.",
        )
    gerar_carrossel_textual(db, carrossel, regenerar=False)
    db.commit()
    db.refresh(carrossel)
    return buscar_carrossel(db, carrossel.id)


@router.post("/carrosseis/{carrossel_id}/regenerar", response_model=CarrosselRead)
def regenerar_carrossel(carrossel_id: int, db: Session = Depends(get_db)):
    carrossel = buscar_carrossel(db, carrossel_id)
    gerar_carrossel_textual(db, carrossel, regenerar=True)
    db.commit()
    db.refresh(carrossel)
    return buscar_carrossel(db, carrossel.id)



@router.post("/carrosseis/{carrossel_id}/assets/gerar", response_model=AssetVisualRead, status_code=status.HTTP_201_CREATED)
def gerar_asset_carrossel(carrossel_id: int, db: Session = Depends(get_db)):
    carrossel = buscar_carrossel(db, carrossel_id)
    asset = gerar_asset_visual(db, carrossel)
    db.commit()
    db.refresh(asset)
    return asset


@router.get("/carrosseis/{carrossel_id}/assets", response_model=list[AssetVisualRead])
def listar_assets_carrossel(carrossel_id: int, db: Session = Depends(get_db)):
    buscar_carrossel(db, carrossel_id)
    return (
        db.query(CarrosselAsset)
        .filter(CarrosselAsset.carrossel_id == carrossel_id)
        .filter(CarrosselAsset.status == ASSET_STATUS_ATIVO)
        .order_by(CarrosselAsset.created_at.desc())
        .all()
    )


@router.delete("/assets/{asset_id}", response_model=AssetVisualRead)
def remover_asset(asset_id: int, db: Session = Depends(get_db)):
    asset = buscar_asset(db, asset_id)
    remover_asset_visual(db, asset)
    for slide in db.query(CarrosselSlide).filter(CarrosselSlide.carrossel_id == asset.carrossel_id).all():
        config = slide.layout_config or {}
        if config.get("asset_id") == asset.id:
            slide.layout_config = {**config, "asset_id": None}
    db.commit()
    db.refresh(asset)
    return asset


@router.post("/carrosseis/{carrossel_id}/renderizar", response_model=CarrosselRead)
def renderizar_carrossel(
    carrossel_id: int,
    payload: RenderizacaoCreate | None = Body(default=None),
    db: Session = Depends(get_db),
):
    carrossel = buscar_carrossel(db, carrossel_id)
    if not carrossel.slides:
        raise HTTPException(status_code=409, detail="Não é possível renderizar sem slides gerados.")
    if len(carrossel.slides) > 20:
        raise HTTPException(status_code=409, detail="Não é possível renderizar mais de 20 slides.")
    opcoes = payload or RenderizacaoCreate()
    asset = None
    if opcoes.asset_id:
        asset = buscar_asset(db, opcoes.asset_id)
        if asset.carrossel_id != carrossel.id or asset.status != ASSET_STATUS_ATIVO:
            raise HTTPException(status_code=404, detail="Asset visual não encontrado para este carrossel.")
    renderizar_carrossel_slides(
        db,
        carrossel,
        template=opcoes.template,
        brand_name=opcoes.brand_name,
        primary_color=opcoes.primary_color,
        asset=asset,
    )
    db.commit()
    db.refresh(carrossel)
    return buscar_carrossel(db, carrossel.id)


@router.get("/carrosseis/{carrossel_id}/slides", response_model=list[SlideRead])
def listar_slides(carrossel_id: int, db: Session = Depends(get_db)):
    buscar_carrossel(db, carrossel_id)
    return (
        db.query(CarrosselSlide)
        .filter(CarrosselSlide.carrossel_id == carrossel_id)
        .order_by(CarrosselSlide.numero_slide.asc())
        .all()
    )


@router.put("/slides/{slide_id}", response_model=SlideRead)
def atualizar_slide(slide_id: int, payload: SlideUpdate, db: Session = Depends(get_db)):
    slide = db.query(CarrosselSlide).filter(CarrosselSlide.id == slide_id).first()
    if slide is None:
        raise HTTPException(status_code=404, detail="Slide não encontrado.")
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(slide, campo, valor)
    registrar_log(
        db,
        carrossel_id=slide.carrossel_id,
        etapa="slide",
        status="ATUALIZADO",
        mensagem="Slide atualizado.",
        detalhes={"slide_id": slide.id, "campos": list(payload.model_dump(exclude_unset=True).keys())},
    )
    db.commit()
    db.refresh(slide)
    return slide


@router.post("/carrosseis/{carrossel_id}/aprovar", response_model=CarrosselRead)
def aprovar_carrossel(carrossel_id: int, db: Session = Depends(get_db)):
    carrossel = buscar_carrossel(db, carrossel_id)
    if not carrossel.slides:
        raise HTTPException(status_code=409, detail="Não é possível aprovar sem slides gerados.")
    carrossel.status = STATUS_APROVADO
    carrossel.aprovado = True
    carrossel.aprovado_em = datetime.utcnow()
    registrar_log(
        db,
        carrossel_id=carrossel.id,
        etapa="aprovacao",
        status="APROVADO",
        mensagem="Carrossel aprovado manualmente.",
    )
    db.commit()
    db.refresh(carrossel)
    return carrossel


@router.post("/carrosseis/{carrossel_id}/rejeitar", response_model=CarrosselRead)
def rejeitar_carrossel(carrossel_id: int, db: Session = Depends(get_db)):
    carrossel = buscar_carrossel(db, carrossel_id)
    if carrossel.status == STATUS_PUBLICADO:
        raise HTTPException(status_code=409, detail="Carrossel publicado não pode ser rejeitado.")
    carrossel.status = STATUS_REJEITADO
    carrossel.aprovado = False
    registrar_log(
        db,
        carrossel_id=carrossel.id,
        etapa="aprovacao",
        status="REJEITADO",
        mensagem="Carrossel rejeitado manualmente.",
    )
    db.commit()
    db.refresh(carrossel)
    return carrossel


@router.post("/carrosseis/{carrossel_id}/agendar", response_model=PublicacaoRead)
def agendar_carrossel(
    carrossel_id: int,
    payload: AgendamentoCreate,
    db: Session = Depends(get_db),
):
    carrossel = buscar_carrossel(db, carrossel_id)
    if carrossel.status != STATUS_APROVADO:
        raise HTTPException(status_code=409, detail="Apenas carrosséis aprovados podem ser agendados.")
    publicacao = Publicacao(
        carrossel_id=carrossel.id,
        plataforma=payload.plataforma,
        agendado_para=payload.agendado_para,
        status=STATUS_AGENDADO,
    )
    carrossel.status = STATUS_AGENDADO
    carrossel.agendado_para = payload.agendado_para
    db.add(publicacao)
    db.flush()
    registrar_log(
        db,
        carrossel_id=carrossel.id,
        etapa="agendamento",
        status="AGENDADO",
        mensagem="Publicação agendada.",
        detalhes={"publicacao_id": publicacao.id, "agendado_para": payload.agendado_para.isoformat()},
    )
    db.commit()
    db.refresh(publicacao)
    return publicacao


@router.put("/publicacoes/{publicacao_id}/reagendar", response_model=PublicacaoRead)
def reagendar_publicacao(
    publicacao_id: int,
    payload: ReagendamentoUpdate,
    db: Session = Depends(get_db),
):
    publicacao = buscar_publicacao(db, publicacao_id)
    if publicacao.status == STATUS_PUBLICADO:
        raise HTTPException(status_code=409, detail="Publicações já publicadas não podem ser reagendadas.")
    if publicacao.status != STATUS_AGENDADO:
        raise HTTPException(status_code=409, detail="Apenas publicações agendadas podem ser reagendadas.")

    anterior = publicacao.agendado_para
    publicacao.agendamento_anterior = anterior
    publicacao.agendado_para = payload.agendado_para
    publicacao.reagendado = True
    publicacao.reagendado_em = datetime.utcnow()
    if payload.plataforma:
        publicacao.plataforma = payload.plataforma

    publicacao.carrossel.agendado_para = payload.agendado_para
    registrar_log(
        db,
        carrossel_id=publicacao.carrossel_id,
        etapa="reagendamento",
        status="REAGENDADO",
        mensagem="Publicação reagendada.",
        detalhes={
            "publicacao_id": publicacao.id,
            "agendamento_anterior": anterior.isoformat(),
            "novo_agendamento": payload.agendado_para.isoformat(),
        },
    )
    db.commit()
    db.refresh(publicacao)
    return publicacao


@router.post("/publicacoes/{publicacao_id}/cancelar", response_model=PublicacaoRead)
def cancelar_publicacao(publicacao_id: int, db: Session = Depends(get_db)):
    publicacao = buscar_publicacao(db, publicacao_id)
    if publicacao.status == STATUS_PUBLICADO:
        raise HTTPException(status_code=409, detail="Publicações já publicadas não podem ser canceladas.")
    publicacao.status = STATUS_CANCELADO
    publicacao.carrossel.status = STATUS_CANCELADO
    registrar_log(
        db,
        carrossel_id=publicacao.carrossel_id,
        etapa="cancelamento",
        status="CANCELADO",
        mensagem="Publicação cancelada.",
        detalhes={"publicacao_id": publicacao.id},
    )
    db.commit()
    db.refresh(publicacao)
    return publicacao


@router.post("/carrosseis/{carrossel_id}/publicar-agora", response_model=PublicacaoRead)
def publicar_agora(carrossel_id: int, db: Session = Depends(get_db)):
    carrossel = buscar_carrossel(db, carrossel_id)
    if carrossel.status == STATUS_PUBLICADO:
        raise HTTPException(status_code=409, detail="Carrossel já publicado.")
    if carrossel.status not in {STATUS_APROVADO, STATUS_AGENDADO}:
        raise HTTPException(status_code=409, detail="Apenas carrosséis aprovados ou agendados podem ser publicados.")

    publicacao = (
        db.query(Publicacao)
        .filter(Publicacao.carrossel_id == carrossel.id)
        .filter(Publicacao.status == STATUS_AGENDADO)
        .order_by(Publicacao.agendado_para.asc())
        .first()
    )
    if publicacao is None:
        publicacao = Publicacao(
            carrossel_id=carrossel.id,
            plataforma="instagram",
            agendado_para=datetime.utcnow(),
            status=STATUS_AGENDADO,
        )
        db.add(publicacao)
        db.flush()

    publicar_mockado(db, publicacao)
    db.commit()
    db.refresh(publicacao)
    return publicacao


@router.get("/publicacoes", response_model=list[PublicacaoRead])
def listar_publicacoes(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return (
        db.query(Publicacao)
        .order_by(Publicacao.agendado_para.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/publicacoes/{publicacao_id}", response_model=PublicacaoRead)
def obter_publicacao(publicacao_id: int, db: Session = Depends(get_db)):
    return buscar_publicacao(db, publicacao_id)


@router.get("/logs", response_model=list[LogExecucaoRead])
def listar_logs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return (
        db.query(LogExecucao)
        .order_by(LogExecucao.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
