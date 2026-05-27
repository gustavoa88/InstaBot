from sqlalchemy import Boolean, Column, ForeignKey, BigInteger, Integer, String, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


STATUS_RASCUNHO = "RASCUNHO"
STATUS_IDEIA_SALVA = "IDEIA_SALVA"
STATUS_GERANDO = "GERANDO"
STATUS_GERANDO_ESTRUTURA = "GERANDO_ESTRUTURA"
STATUS_DESENVOLVENDO_VISUAL = "DESENVOLVENDO_VISUAL"
STATUS_RENDERIZANDO_SLIDES = "RENDERIZANDO_SLIDES"
STATUS_AGUARDANDO_DOWNLOAD = "AGUARDANDO_DOWNLOAD"
STATUS_FEITO_DOWNLOAD = "FEITO_DOWNLOAD"
STATUS_ERRO = "ERRO"
STATUS_AGUARDANDO_APROVACAO = "AGUARDANDO_APROVACAO"

ASSET_STATUS_ATIVO = "ATIVO"
ASSET_STATUS_REMOVIDO = "REMOVIDO"

CARROSSEL_STATUS = {
    STATUS_RASCUNHO,
    STATUS_IDEIA_SALVA,
    STATUS_GERANDO,
    STATUS_GERANDO_ESTRUTURA,
    STATUS_DESENVOLVENDO_VISUAL,
    STATUS_RENDERIZANDO_SLIDES,
    STATUS_AGUARDANDO_DOWNLOAD,
    STATUS_FEITO_DOWNLOAD,
    STATUS_ERRO,
    STATUS_AGUARDANDO_APROVACAO,
}


class Usuario(Base):
    __tablename__ = "usuario"

    id = Column(BigInteger, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    nome = Column(String(150), nullable=False)
    senha_hash = Column(Text, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    configuracao = relationship("UsuarioConfiguracao", back_populates="usuario", uselist=False, cascade="all, delete-orphan")
    carrosseis = relationship("Carrossel", back_populates="usuario", cascade="all, delete-orphan")


class UsuarioConfiguracao(Base):
    __tablename__ = "usuario_configuracao"

    usuario_id = Column(BigInteger, ForeignKey("usuario.id", ondelete="CASCADE"), primary_key=True)
    openai_api_key_encrypted = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    usuario = relationship("Usuario", back_populates="configuracao")


class Carrossel(Base):
    __tablename__ = "carrossel"

    id = Column(BigInteger, primary_key=True, index=True)
    usuario_id = Column(BigInteger, ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False, index=True)

    titulo = Column(String(200))
    ideia_original = Column(Text, nullable=False)

    status = Column(String(50), nullable=False, default=STATUS_IDEIA_SALVA)

    tema = Column(String(100))
    tom = Column(String(100))
    publico_alvo = Column(String(150))
    quantidade_slides = Column(Integer, default=7)

    legenda = Column(Text)
    hashtags = Column(ARRAY(Text))

    prompt_config = Column(JSONB)
    ia_resultado = Column(JSONB)

    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(
        TIMESTAMP,
        server_default=func.now(),
        onupdate=func.now(),
    )

    slides = relationship(
        "CarrosselSlide",
        back_populates="carrossel",
        cascade="all, delete-orphan",
        order_by="CarrosselSlide.numero_slide",
    )
    assets = relationship(
        "CarrosselAsset",
        back_populates="carrossel",
        cascade="all, delete-orphan",
    )
    usuario = relationship("Usuario", back_populates="carrosseis")


class CarrosselAsset(Base):
    __tablename__ = "carrossel_asset"

    id = Column(BigInteger, primary_key=True, index=True)
    carrossel_id = Column(
        BigInteger,
        ForeignKey("carrossel.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    tipo = Column(String(50), nullable=False, default="background")
    status = Column(String(50), nullable=False, default=ASSET_STATUS_ATIVO)
    prompt = Column(Text)
    revised_prompt = Column(Text)
    asset_path = Column(Text)
    asset_url = Column(Text)
    modelo = Column(String(100))
    provider_response = Column(JSONB)

    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(
        TIMESTAMP,
        server_default=func.now(),
        onupdate=func.now(),
    )

    carrossel = relationship("Carrossel", back_populates="assets")


class CarrosselSlide(Base):
    __tablename__ = "carrossel_slide"

    id = Column(BigInteger, primary_key=True, index=True)
    carrossel_id = Column(
        BigInteger,
        ForeignKey("carrossel.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    numero_slide = Column(Integer, nullable=False)
    titulo = Column(Text)
    texto_principal = Column(Text)
    texto_secundario = Column(Text)
    observacao_visual = Column(Text)

    imagem_path = Column(Text)
    imagem_url = Column(Text)

    layout_config = Column(JSONB)

    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(
        TIMESTAMP,
        server_default=func.now(),
        onupdate=func.now(),
    )

    carrossel = relationship("Carrossel", back_populates="slides")


class LogExecucao(Base):
    __tablename__ = "log_execucao"

    id = Column(BigInteger, primary_key=True, index=True)
    carrossel_id = Column(BigInteger, index=True)
    etapa = Column(String(100))
    status = Column(String(50))
    mensagem = Column(Text)
    detalhes = Column(JSONB)
    created_at = Column(TIMESTAMP, server_default=func.now())
