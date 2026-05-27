from datetime import datetime
from io import BytesIO

from fastapi import APIRouter, Body, Depends, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.config import STORAGE_PATH
from app.database import get_db
from app.models.carrossel import (
    ASSET_STATUS_ATIVO,
    Carrossel,
    CarrosselAsset,
    CarrosselSlide,
    LogExecucao,
    Usuario,
    STATUS_AGUARDANDO_APROVACAO,
)
from app.schemas.carrossel import (
    AssetVisualRead,
    CarrosselCreate,
    CarrosselRead,
    CarrosselUpdate,
    LogExecucaoRead,
    RenderizacaoCreate,
    SlideRead,
    SlideUpdate,
)
from app.services.generation_service import gerar_carrossel_textual
from app.services.export_service import export_carousel_to_zip
from app.services.image_asset_service import gerar_asset_visual, remover_asset_visual
from app.services.log_service import registrar_log
from app.security import get_current_user
from app.services.render_service import renderizar_carrossel_slides
from app.services.user_config_service import credentials_for_user

router = APIRouter(dependencies=[Depends(get_current_user)])


def buscar_carrossel(db: Session, carrossel_id: int, usuario: Usuario) -> Carrossel:
    carrossel = (
        db.query(Carrossel)
        .options(joinedload(Carrossel.slides), joinedload(Carrossel.assets))
        .filter(Carrossel.id == carrossel_id)
        .filter(Carrossel.usuario_id == usuario.id)
        .first()
    )
    if carrossel is None:
        raise HTTPException(status_code=404, detail="Carrossel não encontrado.")
    return carrossel


def buscar_asset(db: Session, asset_id: int, usuario: Usuario) -> CarrosselAsset:
    asset = (
        db.query(CarrosselAsset)
        .join(Carrossel, CarrosselAsset.carrossel_id == Carrossel.id)
        .filter(CarrosselAsset.id == asset_id)
        .filter(Carrossel.usuario_id == usuario.id)
        .first()
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset visual não encontrado.")
    return asset


@router.post("/carrosseis", response_model=CarrosselRead, status_code=status.HTTP_201_CREATED)
def criar_carrossel(payload: CarrosselCreate, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    dados = payload.model_dump(exclude={"observacoes_adicionais"})
    carrossel = Carrossel(
        usuario_id=usuario.id,
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
def listar_carrosseis(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    return (
        db.query(Carrossel)
        .options(joinedload(Carrossel.slides), joinedload(Carrossel.assets))
        .filter(Carrossel.usuario_id == usuario.id)
        .order_by(Carrossel.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/carrosseis/{carrossel_id}", response_model=CarrosselRead)
def obter_carrossel(carrossel_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    return buscar_carrossel(db, carrossel_id, usuario)


@router.get("/carrosseis/{carrossel_id}/exportar")
def exportar_carrossel(carrossel_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    carrossel = buscar_carrossel(db, carrossel_id, usuario)
    try:
        zip_bytes = export_carousel_to_zip(db, carrossel, STORAGE_PATH)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    filename = f"carousel_{carrossel.id}_{timestamp}.zip"
    headers = {"Content-Disposition": f"attachment; filename=\"{filename}\""}
    return StreamingResponse(BytesIO(zip_bytes), media_type="application/zip", headers=headers)


@router.put("/carrosseis/{carrossel_id}", response_model=CarrosselRead)
def atualizar_carrossel(
    carrossel_id: int,
    payload: CarrosselUpdate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    carrossel = buscar_carrossel(db, carrossel_id, usuario)
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
def remover_carrossel(carrossel_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    carrossel = buscar_carrossel(db, carrossel_id, usuario)
    db.delete(carrossel)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/carrosseis/{carrossel_id}/gerar", response_model=CarrosselRead)
def gerar_carrossel(carrossel_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    carrossel = buscar_carrossel(db, carrossel_id, usuario)
    if carrossel.slides:
        raise HTTPException(
            status_code=409,
            detail="Carrossel já possui slides. Use /regenerar para substituir.",
        )
    gerar_carrossel_textual(db, carrossel, credentials=credentials_for_user(db, usuario), regenerar=False, usuario=usuario)
    db.commit()
    db.refresh(carrossel)
    return buscar_carrossel(db, carrossel.id, usuario)


@router.post("/carrosseis/{carrossel_id}/regenerar", response_model=CarrosselRead)
def regenerar_carrossel(carrossel_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    carrossel = buscar_carrossel(db, carrossel_id, usuario)
    gerar_carrossel_textual(db, carrossel, credentials=credentials_for_user(db, usuario), regenerar=True, usuario=usuario)
    db.commit()
    db.refresh(carrossel)
    return buscar_carrossel(db, carrossel.id, usuario)



@router.post("/carrosseis/{carrossel_id}/assets/gerar", response_model=AssetVisualRead, status_code=status.HTTP_201_CREATED)
def gerar_asset_carrossel(carrossel_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    carrossel = buscar_carrossel(db, carrossel_id, usuario)
    credentials = credentials_for_user(db, usuario)
    asset = gerar_asset_visual(db, carrossel, api_key=credentials.openai_api_key, strict_config=True, usuario=usuario)
    db.commit()
    db.refresh(asset)
    return asset


@router.get("/carrosseis/{carrossel_id}/assets", response_model=list[AssetVisualRead])
def listar_assets_carrossel(carrossel_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    buscar_carrossel(db, carrossel_id, usuario)
    return (
        db.query(CarrosselAsset)
        .filter(CarrosselAsset.carrossel_id == carrossel_id)
        .filter(CarrosselAsset.status == ASSET_STATUS_ATIVO)
        .order_by(CarrosselAsset.created_at.desc())
        .all()
    )


@router.delete("/assets/{asset_id}", response_model=AssetVisualRead)
def remover_asset(asset_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    asset = buscar_asset(db, asset_id, usuario)
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
    usuario: Usuario = Depends(get_current_user),
):
    carrossel = buscar_carrossel(db, carrossel_id, usuario)
    if not carrossel.slides:
        raise HTTPException(status_code=409, detail="Não é possível renderizar sem slides gerados.")
    opcoes = payload or RenderizacaoCreate()
    asset = None
    if opcoes.asset_id:
        asset = buscar_asset(db, opcoes.asset_id, usuario)
        if asset.carrossel_id != carrossel.id or asset.status != ASSET_STATUS_ATIVO:
            raise HTTPException(status_code=404, detail="Asset visual não encontrado para este carrossel.")
        # In OpenAI-only mode, selected asset support is currently ignored.
        # Keep validation for the provided asset_id, but render with OpenAI anyway.
        asset = None
    credentials = credentials_for_user(db, usuario)
    if not credentials.openai_api_key:
        raise HTTPException(status_code=409, detail="Configure sua OPENAI_API_KEY na tela de configurações antes de renderizar com IA.")
    renderizar_carrossel_slides(
        db,
        carrossel,
        template=opcoes.template,
        brand_name=opcoes.brand_name,
        primary_color=opcoes.primary_color,
        asset=asset,
        api_key=credentials.openai_api_key,
        usuario=usuario,
    )
    db.commit()
    db.refresh(carrossel)
    return buscar_carrossel(db, carrossel.id, usuario)


@router.get("/carrosseis/{carrossel_id}/slides", response_model=list[SlideRead])
def listar_slides(carrossel_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    buscar_carrossel(db, carrossel_id, usuario)
    return (
        db.query(CarrosselSlide)
        .filter(CarrosselSlide.carrossel_id == carrossel_id)
        .order_by(CarrosselSlide.numero_slide.asc())
        .all()
    )


@router.put("/slides/{slide_id}", response_model=SlideRead)
def atualizar_slide(slide_id: int, payload: SlideUpdate, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    slide = (
        db.query(CarrosselSlide)
        .join(Carrossel, CarrosselSlide.carrossel_id == Carrossel.id)
        .filter(CarrosselSlide.id == slide_id)
        .filter(Carrossel.usuario_id == usuario.id)
        .first()
    )
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


@router.get("/logs", response_model=list[LogExecucaoRead])
def listar_logs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    return (
        db.query(LogExecucao)
        .outerjoin(Carrossel, LogExecucao.carrossel_id == Carrossel.id)
        .filter(or_(Carrossel.usuario_id == usuario.id, LogExecucao.carrossel_id.is_(None) if usuario.is_admin else False))
        .order_by(LogExecucao.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
