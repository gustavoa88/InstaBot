from sqlalchemy import Boolean, Column, ForeignKey, BigInteger, Integer, String, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


STATUS_RASCUNHO = "RASCUNHO"
STATUS_GERANDO = "GERANDO"
STATUS_AGUARDANDO_APROVACAO = "AGUARDANDO_APROVACAO"
STATUS_APROVADO = "APROVADO"
STATUS_REJEITADO = "REJEITADO"
STATUS_AGENDADO = "AGENDADO"
STATUS_CANCELADO = "CANCELADO"
STATUS_PUBLICADO = "PUBLICADO"
STATUS_ERRO_PUBLICACAO = "ERRO_PUBLICACAO"

CARROSSEL_STATUS = {
    STATUS_RASCUNHO,
    STATUS_GERANDO,
    STATUS_AGUARDANDO_APROVACAO,
    STATUS_APROVADO,
    STATUS_REJEITADO,
    STATUS_AGENDADO,
    STATUS_CANCELADO,
    STATUS_PUBLICADO,
    STATUS_ERRO_PUBLICACAO,
}


class Carrossel(Base):
    __tablename__ = "carrossel"

    id = Column(BigInteger, primary_key=True, index=True)

    titulo = Column(String(200))
    ideia_original = Column(Text, nullable=False)

    status = Column(String(50), nullable=False, default=STATUS_RASCUNHO)

    tema = Column(String(100))
    tom = Column(String(100))
    publico_alvo = Column(String(150))
    quantidade_slides = Column(Integer, default=7)

    legenda = Column(Text)
    hashtags = Column(ARRAY(Text))

    prompt_config = Column(JSONB)
    ia_resultado = Column(JSONB)

    aprovado = Column(Boolean, default=False)
    aprovado_em = Column(TIMESTAMP)
    agendado_para = Column(TIMESTAMP)
    publicado_em = Column(TIMESTAMP)

    erro_publicacao = Column(Text)

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
    publicacoes = relationship(
        "Publicacao",
        back_populates="carrossel",
        cascade="all, delete-orphan",
    )


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

    aprovado = Column(Boolean, default=True)

    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(
        TIMESTAMP,
        server_default=func.now(),
        onupdate=func.now(),
    )

    carrossel = relationship("Carrossel", back_populates="slides")


class Publicacao(Base):
    __tablename__ = "publicacao"

    id = Column(BigInteger, primary_key=True, index=True)
    carrossel_id = Column(
        BigInteger,
        ForeignKey("carrossel.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    plataforma = Column(String(50), nullable=False)
    status = Column(String(50), default=STATUS_AGENDADO)

    agendado_para = Column(TIMESTAMP, nullable=False)
    publicado_em = Column(TIMESTAMP)

    external_post_id = Column(Text)
    resposta_api = Column(JSONB)
    erro = Column(Text)

    reagendado = Column(Boolean, default=False)
    reagendado_em = Column(TIMESTAMP)
    agendamento_anterior = Column(TIMESTAMP)

    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(
        TIMESTAMP,
        server_default=func.now(),
        onupdate=func.now(),
    )

    carrossel = relationship("Carrossel", back_populates="publicacoes")


class LogExecucao(Base):
    __tablename__ = "log_execucao"

    id = Column(BigInteger, primary_key=True, index=True)
    carrossel_id = Column(BigInteger, index=True)
    etapa = Column(String(100))
    status = Column(String(50))
    mensagem = Column(Text)
    detalhes = Column(JSONB)
    created_at = Column(TIMESTAMP, server_default=func.now())
