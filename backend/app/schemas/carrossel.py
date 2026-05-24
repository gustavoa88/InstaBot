from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CarrosselCreate(BaseModel):
    titulo: str | None = Field(default=None, max_length=200)
    ideia_original: str = Field(min_length=1, max_length=5000)
    tema: str | None = Field(default=None, max_length=100)
    tom: str | None = Field(default=None, max_length=100)
    publico_alvo: str | None = Field(default=None, max_length=150)
    quantidade_slides: int = Field(default=7, ge=1, le=20)
    observacoes_adicionais: str | None = Field(default=None, max_length=1000)


class CarrosselUpdate(BaseModel):
    titulo: str | None = Field(default=None, max_length=200)
    ideia_original: str | None = Field(default=None, min_length=1, max_length=5000)
    tema: str | None = Field(default=None, max_length=100)
    tom: str | None = Field(default=None, max_length=100)
    publico_alvo: str | None = Field(default=None, max_length=150)
    quantidade_slides: int | None = Field(default=None, ge=1, le=20)
    legenda: str | None = Field(default=None, max_length=5000)
    hashtags: list[str] | None = Field(default=None, max_length=30)
    prompt_config: dict[str, Any] | None = None


class SlideUpdate(BaseModel):
    titulo: str | None = Field(default=None, max_length=300)
    texto_principal: str | None = Field(default=None, max_length=2000)
    texto_secundario: str | None = Field(default=None, max_length=1000)
    observacao_visual: str | None = Field(default=None, max_length=1000)
    imagem_path: str | None = Field(default=None, max_length=1000)
    imagem_url: str | None = Field(default=None, max_length=1000)
    layout_config: dict[str, Any] | None = None
    aprovado: bool | None = None


class AgendamentoCreate(BaseModel):
    agendado_para: datetime
    plataforma: str = Field(default="instagram", max_length=50)


class ReagendamentoUpdate(BaseModel):
    agendado_para: datetime
    plataforma: str | None = Field(default=None, max_length=50)


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
