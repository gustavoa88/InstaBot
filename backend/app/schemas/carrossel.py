from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CarrosselCreate(BaseModel):
    titulo: str | None = Field(default=None, max_length=200)
    ideia_original: str
    tema: str | None = None
    tom: str | None = None
    publico_alvo: str | None = None
    quantidade_slides: int = Field(default=7, ge=1, le=20)
    observacoes_adicionais: str | None = None


class CarrosselUpdate(BaseModel):
    titulo: str | None = Field(default=None, max_length=200)
    ideia_original: str | None = None
    tema: str | None = None
    tom: str | None = None
    publico_alvo: str | None = None
    quantidade_slides: int | None = Field(default=None, ge=1, le=20)
    legenda: str | None = None
    hashtags: list[str] | None = None
    prompt_config: dict[str, Any] | None = None


class SlideUpdate(BaseModel):
    titulo: str | None = None
    texto_principal: str | None = None
    texto_secundario: str | None = None
    observacao_visual: str | None = None
    imagem_path: str | None = None
    imagem_url: str | None = None
    layout_config: dict[str, Any] | None = None
    aprovado: bool | None = None


class AgendamentoCreate(BaseModel):
    agendado_para: datetime
    plataforma: str = "instagram"


class ReagendamentoUpdate(BaseModel):
    agendado_para: datetime
    plataforma: str | None = None


class SlideRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    carrossel_id: int
    numero_slide: int
    titulo: str | None = None
    texto_principal: str | None = None
    texto_secundario: str | None = None
    observacao_visual: str | None = None
    imagem_path: str | None = None
    imagem_url: str | None = None
    layout_config: dict[str, Any] | None = None
    aprovado: bool
    created_at: datetime
    updated_at: datetime


class PublicacaoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    carrossel_id: int
    plataforma: str
    status: str
    agendado_para: datetime
    publicado_em: datetime | None = None
    external_post_id: str | None = None
    resposta_api: dict[str, Any] | None = None
    erro: str | None = None
    reagendado: bool
    reagendado_em: datetime | None = None
    agendamento_anterior: datetime | None = None
    created_at: datetime
    updated_at: datetime


class LogExecucaoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    carrossel_id: int | None = None
    etapa: str | None = None
    status: str | None = None
    mensagem: str | None = None
    detalhes: dict[str, Any] | None = None
    created_at: datetime


class CarrosselRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    titulo: str | None = None
    ideia_original: str
    status: str
    tema: str | None = None
    tom: str | None = None
    publico_alvo: str | None = None
    quantidade_slides: int | None = None
    legenda: str | None = None
    hashtags: list[str] | None = None
    prompt_config: dict[str, Any] | None = None
    ia_resultado: dict[str, Any] | None = None
    aprovado: bool
    aprovado_em: datetime | None = None
    agendado_para: datetime | None = None
    publicado_em: datetime | None = None
    erro_publicacao: str | None = None
    created_at: datetime
    updated_at: datetime
    slides: list[SlideRead] = Field(default_factory=list)
    publicacoes: list[PublicacaoRead] = Field(default_factory=list)
