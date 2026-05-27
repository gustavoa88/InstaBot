from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CarrosselCreate(BaseModel):
    titulo: str | None = Field(default=None, max_length=200)
    ideia_original: str = Field(min_length=1, max_length=5000)
    tema: str | None = Field(default=None, max_length=100)
    tom: str | None = Field(default=None, max_length=100)
    publico_alvo: str | None = Field(default=None, max_length=150)
    quantidade_slides: int = Field(default=7, ge=1, le=7)
    observacoes_adicionais: str | None = Field(default=None, max_length=1000)


class CarrosselUpdate(BaseModel):
    titulo: str | None = Field(default=None, max_length=200)
    ideia_original: str | None = Field(default=None, min_length=1, max_length=5000)
    tema: str | None = Field(default=None, max_length=100)
    tom: str | None = Field(default=None, max_length=100)
    publico_alvo: str | None = Field(default=None, max_length=150)
    quantidade_slides: int | None = Field(default=None, ge=1, le=7)
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


class RenderizacaoCreate(BaseModel):
    template: str | None = Field(default=None, max_length=50)
    brand_name: str | None = Field(default=None, max_length=80)
    primary_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    asset_id: int | None = Field(default=None, ge=1)
    aspect_ratio: Literal["1:1", "1.91:1", "4:5"] = "4:5"


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
    created_at: datetime
    updated_at: datetime


class AssetVisualRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    carrossel_id: int
    tipo: str
    status: str
    prompt: str | None = None
    revised_prompt: str | None = None
    asset_path: str | None = None
    asset_url: str | None = None
    modelo: str | None = None
    provider_response: dict[str, Any] | None = None
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
    created_at: datetime
    updated_at: datetime
    slides: list[SlideRead] = Field(default_factory=list)
    assets: list[AssetVisualRead] = Field(default_factory=list)


class UsuarioRegister(BaseModel):
    nome: str = Field(min_length=1, max_length=150)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=200)


class UsuarioLogin(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=1, max_length=200)


class UsuarioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    nome: str
    is_admin: bool
    created_at: datetime


class TokenRead(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioRead


class ConfiguracaoUpdate(BaseModel):
    openai_api_key: str | None = Field(default=None, max_length=500)


class ConfiguracaoRead(BaseModel):
    openai_configurado: bool
    openai_api_key_masked: str | None = None
