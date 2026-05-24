from pydantic import BaseModel


class CarrosselCreate(BaseModel):
    titulo: str
    ideia_original: str
    tema: str | None = None
    tom: str | None = None
    publico_alvo: str | None = None
