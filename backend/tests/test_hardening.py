from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.schemas.carrossel import CarrosselCreate, SlideUpdate
from app.security import require_admin_token
from app.services import media_cleanup_service, render_service


class FakeDb:
    def __init__(self):
        self.added = []

    def add(self, item):
        self.added.append(item)


def test_admin_token_blocks_missing_and_accepts_configured(monkeypatch):
    monkeypatch.setattr("app.security.ADMIN_API_TOKEN", "secret")

    with pytest.raises(HTTPException) as exc_info:
        require_admin_token(None)
    assert exc_info.value.status_code == 401

    require_admin_token("secret")


def test_payload_limits_reject_oversized_text():
    with pytest.raises(ValidationError):
        CarrosselCreate(ideia_original="x" * 5001)

    with pytest.raises(ValidationError):
        SlideUpdate(texto_principal="x" * 2001)


def test_storage_path_resolver_rejects_traversal(tmp_path):
    storage_root = tmp_path.resolve()
    assert media_cleanup_service._resolver_storage_path("carrosseis/1/slides/a.png", storage_root) == (storage_root / "carrosseis/1/slides/a.png").resolve()
    assert media_cleanup_service._resolver_storage_path("../outside.png", storage_root) is None
    assert media_cleanup_service._resolver_storage_path(str(storage_root / "absolute.png"), storage_root) is None


def test_render_service_creates_relative_png_and_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(render_service, "STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(render_service, "PUBLIC_BASE_URL", "")

    slide = SimpleNamespace(
        id=1,
        carrossel_id=10,
        numero_slide=1,
        titulo="Slide de teste",
        texto_principal="Texto principal curto para validar renderização",
        texto_secundario=None,
        observacao_visual="Briefing visual simples",
        imagem_path=None,
        imagem_url=None,
        layout_config={},
    )
    carrossel = SimpleNamespace(id=10, titulo="Carrossel", tema="Tema", slides=[slide])

    render_service.renderizar_carrossel_slides(FakeDb(), carrossel)

    assert slide.imagem_path == "carrosseis/10/slides/slide-01.png"
    assert slide.imagem_url.startswith("/storage/carrosseis/10/slides/slide-01.png?v=")
    assert slide.layout_config["renderer"] == "pillow"
    rendered = tmp_path / slide.imagem_path
    assert rendered.exists()
    assert rendered.read_bytes().startswith(b"\x89PNG")
