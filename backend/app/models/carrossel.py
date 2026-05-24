from sqlalchemy import Column, BigInteger, String, Text, TIMESTAMP
from sqlalchemy.sql import func

from app.database import Base



class Carrossel(Base):
    __tablename__ = "carrossel"

    id = Column(BigInteger, primary_key=True, index=True)

    titulo = Column(String(200))
    ideia_original = Column(Text, nullable=False)

    status = Column(String(50), default="RASCUNHO")

    tema = Column(String(100))
    tom = Column(String(100))
    publico_alvo = Column(String(150))

    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(
        TIMESTAMP,
        server_default=func.now(),
        onupdate=func.now()
    )
