from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from PIL import Image
from pydantic import ValidationError

from app.schemas.carrossel import CarrosselCreate, RenderizacaoCreate, SlideUpdate
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

    with pytest.raises(ValidationError):
        RenderizacaoCreate(primary_color="azul")


def test_storage_path_resolver_rejects_traversal(tmp_path):
    storage_root = tmp_path.resolve()
    assert media_cleanup_service._resolver_storage_path("carrosseis/1/slides/a.png", storage_root) == (storage_root / "carrosseis/1/slides/a.png").resolve()
    assert media_cleanup_service._resolver_storage_path("../outside.png", storage_root) is None
    assert media_cleanup_service._resolver_storage_path(str(storage_root / "absolute.png"), storage_root) is None


def _fake_carrossel(template_id=10):
    slide = SimpleNamespace(
        id=1,
        carrossel_id=template_id,
        numero_slide=1,
        titulo="Slide de teste",
        texto_principal="Texto principal curto para validar renderização com quebra de texto previsível",
        texto_secundario="Complemento curto para validar o bloco secundário.",
        observacao_visual="Briefing visual simples com indicação de imagem e composição.",
        imagem_path=None,
        imagem_url=None,
        layout_config={},
    )
    carrossel = SimpleNamespace(id=template_id, titulo="Carrossel", tema="Tema", slides=[slide])
    return carrossel, slide


def test_render_service_creates_relative_png_and_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(render_service, "STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(render_service, "PUBLIC_BASE_URL", "")
    carrossel, slide = _fake_carrossel()

    render_service.renderizar_carrossel_slides(
        FakeDb(),
        carrossel,
        template="clean_editorial",
        brand_name="InstaBot",
        primary_color="#336699",
    )

    assert slide.imagem_path == "carrosseis/10/slides/slide-01.png"
    assert slide.imagem_url.startswith("/storage/carrosseis/10/slides/slide-01.png?v=")
    assert slide.layout_config["renderer"] == "pillow"
    assert slide.layout_config["template"] == "clean_editorial"
    assert slide.layout_config["brand_name"] == "InstaBot"
    assert slide.layout_config["primary_color"] == "#336699"
    rendered = tmp_path / slide.imagem_path
    assert rendered.exists()
    assert rendered.read_bytes().startswith(b"\x89PNG")
    with Image.open(rendered) as image:
        assert image.size == (1080, 1350)


@pytest.mark.parametrize("template", ["clean_editorial", "bold_contrast", "soft_brand"])
def test_render_service_supports_visual_templates(tmp_path, monkeypatch, template):
    monkeypatch.setattr(render_service, "STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(render_service, "PUBLIC_BASE_URL", "")
    carrossel, slide = _fake_carrossel(template_id=20)

    render_service.renderizar_carrossel_slides(FakeDb(), carrossel, template=template)

    assert slide.layout_config["template"] == template
    with Image.open(tmp_path / slide.imagem_path) as image:
        assert image.size == (1080, 1350)
