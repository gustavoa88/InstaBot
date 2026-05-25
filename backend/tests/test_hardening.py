from pathlib import Path
import base64
from io import BytesIO
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from PIL import Image
from pydantic import ValidationError

from app.schemas.carrossel import CarrosselCreate, RenderizacaoCreate, SlideUpdate
from app.security import require_admin_token
from app.models.carrossel import CarrosselSlide, STATUS_AGUARDANDO_APROVACAO
from app.services import ai_service, image_asset_service, media_cleanup_service, render_service


class FakeDb:
    def __init__(self):
        self.added = []
        self.committed = False

    def add(self, item):
        self.added.append(item)

    def flush(self):
        for index, item in enumerate(self.added, start=1):
            if hasattr(item, "id") and getattr(item, "id", None) is None:
                item.id = index

    def commit(self):
        self.committed = True


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



def test_image_asset_fallback_creates_relative_png(tmp_path, monkeypatch):
    monkeypatch.setattr(image_asset_service, "OPENAI_API_KEY", "")
    monkeypatch.setattr(image_asset_service, "STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(image_asset_service, "PUBLIC_BASE_URL", "")
    carrossel, _slide = _fake_carrossel(template_id=30)
    carrossel.ideia_original = "Ideia para asset visual"
    carrossel.publico_alvo = "Criadores"
    carrossel.tom = "profissional"
    carrossel.prompt_config = {}

    asset = image_asset_service.gerar_asset_visual(FakeDb(), carrossel)

    assert asset.asset_path.startswith("carrosseis/30/assets/asset-")
    assert asset.asset_url.startswith("/storage/carrosseis/30/assets/asset-")
    assert asset.modelo == image_asset_service.FALLBACK_MODEL
    rendered = tmp_path / asset.asset_path
    assert rendered.exists()
    assert rendered.read_bytes().startswith(b"\x89PNG")


def test_image_asset_limit_blocks_without_openai_call(monkeypatch):
    monkeypatch.setattr(image_asset_service, "OPENAI_IMAGE_DAILY_REQUEST_LIMIT", 1)
    monkeypatch.setattr(image_asset_service, "OPENAI_IMAGE_CARROSSEL_REQUEST_LIMIT", 2)
    monkeypatch.setattr(image_asset_service, "_count_openai_image_calls", lambda *args, **kwargs: 1)
    carrossel, _slide = _fake_carrossel(template_id=31)

    with pytest.raises(HTTPException) as exc_info:
        image_asset_service._verify_limits(FakeDb(), carrossel)

    assert exc_info.value.status_code == 429


def test_global_image_asset_falls_back_when_openai_limit_is_reached(tmp_path, monkeypatch):
    monkeypatch.setattr(image_asset_service, "STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(image_asset_service, "PUBLIC_BASE_URL", "")
    monkeypatch.setattr(image_asset_service, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(image_asset_service, "OPENAI_IMAGE_CARROSSEL_REQUEST_LIMIT", 2)
    monkeypatch.setattr(image_asset_service, "_count_openai_image_calls", lambda *args, **kwargs: 2)
    carrossel, _slide = _fake_carrossel(template_id=32)
    carrossel.ideia_original = "Ideia para asset visual"
    carrossel.publico_alvo = "Criadores"
    carrossel.tom = "profissional"
    carrossel.prompt_config = {}

    asset = image_asset_service.gerar_asset_visual(FakeDb(), carrossel)

    assert asset.modelo == image_asset_service.FALLBACK_MODEL
    assert asset.provider_response["fallback_reason"] == "limite_openai"
    assert asset.provider_response["limit"]["escopo"] == "por carrossel"
    assert asset.asset_path.startswith("carrosseis/32/assets/asset-")
    assert (tmp_path / asset.asset_path).exists()


def test_render_service_creates_relative_png_and_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(render_service, "STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(render_service, "PUBLIC_BASE_URL", "")
    monkeypatch.setattr(image_asset_service, "STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(image_asset_service, "PUBLIC_BASE_URL", "")
    monkeypatch.setattr(image_asset_service, "OPENAI_API_KEY", "")
    carrossel, slide = _fake_carrossel()

    asset_path = tmp_path / "carrosseis/10/assets/asset-test.png"
    asset_path.parent.mkdir(parents=True)
    Image.new("RGB", (1024, 1536), (40, 80, 120)).save(asset_path)
    asset = SimpleNamespace(id=99, asset_path="carrosseis/10/assets/asset-test.png")

    render_service.renderizar_carrossel_slides(
        FakeDb(),
        carrossel,
        template="clean_editorial",
        brand_name="InstaBot",
        primary_color="#336699",
        asset=asset,
    )

    assert slide.imagem_path == "carrosseis/10/slides/slide-01.png"
    assert slide.imagem_url.startswith("/storage/carrosseis/10/slides/slide-01.png?v=")
    assert slide.layout_config["renderer"] == "pillow"
    assert slide.layout_config["template"] == "clean_editorial"
    assert slide.layout_config["brand_name"] == "InstaBot"
    assert slide.layout_config["primary_color"] == "#336699"
    assert slide.layout_config["asset_id"] != 99
    assert slide.layout_config["slide_asset_path"].startswith("carrosseis/10/assets/slide-01-asset-")
    assert "Briefing visual simples" in slide.layout_config["slide_asset_prompt"]
    rendered = tmp_path / slide.imagem_path
    assert rendered.exists()
    assert rendered.read_bytes().startswith(b"\x89PNG")
    with Image.open(rendered) as image:
        assert image.size == (1080, 1350)


def test_clean_editorial_uses_slide_asset_as_large_hero(tmp_path, monkeypatch):
    monkeypatch.setattr(render_service, "STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(render_service, "PUBLIC_BASE_URL", "")
    monkeypatch.setattr(image_asset_service, "OPENAI_API_KEY", "")
    carrossel, slide = _fake_carrossel(template_id=18)
    asset_path = tmp_path / "carrosseis/18/assets/slide-blue.png"
    asset_path.parent.mkdir(parents=True)
    Image.new("RGB", (1024, 1536), (18, 74, 190)).save(asset_path)

    def fake_slide_asset(*_args, **_kwargs):
        return SimpleNamespace(
            id=501,
            asset_path="carrosseis/18/assets/slide-blue.png",
            prompt="Briefing visual simples com azul editorial.",
            provider_response={"prompt_hash": "blue-hero"},
        )

    monkeypatch.setattr(render_service, "gerar_asset_visual_slide", fake_slide_asset)

    render_service.renderizar_carrossel_slides(FakeDb(), carrossel, template="clean_editorial", primary_color="#336699")

    with Image.open(tmp_path / slide.imagem_path) as image:
        assert image.size == (1080, 1350)
        red, green, blue = image.getpixel((540, 260))
        assert blue > red
        assert blue > green


@pytest.mark.parametrize("template", ["clean_editorial", "bold_contrast", "soft_brand"])
def test_render_service_supports_visual_templates(tmp_path, monkeypatch, template):
    monkeypatch.setattr(render_service, "STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(render_service, "PUBLIC_BASE_URL", "")
    monkeypatch.setattr(image_asset_service, "STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(image_asset_service, "PUBLIC_BASE_URL", "")
    monkeypatch.setattr(image_asset_service, "OPENAI_API_KEY", "")
    carrossel, slide = _fake_carrossel(template_id=20)

    render_service.renderizar_carrossel_slides(FakeDb(), carrossel, template=template)

    assert slide.layout_config["template"] == template
    with Image.open(tmp_path / slide.imagem_path) as image:
        assert image.size == (1080, 1350)


def test_render_service_generates_distinct_fallback_asset_per_slide(tmp_path, monkeypatch):
    monkeypatch.setattr(render_service, "STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(render_service, "PUBLIC_BASE_URL", "")
    monkeypatch.setattr(image_asset_service, "STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(image_asset_service, "PUBLIC_BASE_URL", "")
    monkeypatch.setattr(image_asset_service, "OPENAI_API_KEY", "")
    carrossel, first_slide = _fake_carrossel(template_id=40)
    second_slide = SimpleNamespace(
        id=2,
        carrossel_id=40,
        numero_slide=2,
        titulo="Segundo slide",
        texto_principal="Outro texto principal para validar asset unico",
        texto_secundario=None,
        observacao_visual="Cena abstrata com formas diagonais e cor diferente.",
        imagem_path=None,
        imagem_url=None,
        layout_config={},
    )
    carrossel.slides = [first_slide, second_slide]
    db = FakeDb()

    render_service.renderizar_carrossel_slides(db, carrossel, template="clean_editorial")

    first_asset = tmp_path / first_slide.layout_config["slide_asset_path"]
    second_asset = tmp_path / second_slide.layout_config["slide_asset_path"]
    assert first_slide.layout_config["slide_asset_path"] != second_slide.layout_config["slide_asset_path"]
    assert first_slide.layout_config["slide_asset_prompt_hash"] != second_slide.layout_config["slide_asset_prompt_hash"]
    assert "Briefing visual simples" in first_slide.layout_config["slide_asset_prompt"]
    assert "formas diagonais" in second_slide.layout_config["slide_asset_prompt"]
    assert first_asset.exists()
    assert second_asset.exists()
    assert first_asset.read_bytes() != second_asset.read_bytes()


def test_render_service_reuses_slide_asset_when_prompt_is_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(render_service, "STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(render_service, "PUBLIC_BASE_URL", "")
    monkeypatch.setattr(image_asset_service, "STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(image_asset_service, "PUBLIC_BASE_URL", "")
    monkeypatch.setattr(image_asset_service, "OPENAI_API_KEY", "")
    carrossel, slide = _fake_carrossel(template_id=41)
    db = FakeDb()

    render_service.renderizar_carrossel_slides(db, carrossel, template="clean_editorial")
    assets_after_first_render = [item for item in db.added if getattr(item, "tipo", None) == "slide_background"]
    first_asset_id = slide.layout_config["slide_asset_id"]

    render_service.renderizar_carrossel_slides(db, carrossel, template="clean_editorial")
    assets_after_second_render = [item for item in db.added if getattr(item, "tipo", None) == "slide_background"]

    assert len(assets_after_first_render) == 1
    assert len(assets_after_second_render) == 1
    assert slide.layout_config["slide_asset_id"] == first_asset_id


def test_slide_asset_generation_falls_back_when_openai_limit_is_reached(tmp_path, monkeypatch):
    monkeypatch.setattr(image_asset_service, "STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(image_asset_service, "PUBLIC_BASE_URL", "")
    monkeypatch.setattr(image_asset_service, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(image_asset_service, "OPENAI_IMAGE_CARROSSEL_REQUEST_LIMIT", 2)
    monkeypatch.setattr(image_asset_service, "_count_openai_image_calls", lambda *args, **kwargs: 2)
    carrossel, slide = _fake_carrossel(template_id=42)
    db = FakeDb()

    asset = image_asset_service.gerar_asset_visual_slide(db, carrossel, slide)

    assert asset.modelo == image_asset_service.FALLBACK_MODEL
    assert asset.provider_response["fallback_reason"] == "limite_openai"
    assert asset.provider_response["prompt_hash"]
    assert (tmp_path / asset.asset_path).exists()


def test_render_service_finishes_with_slide_fallback_when_openai_limit_is_reached(tmp_path, monkeypatch):
    monkeypatch.setattr(render_service, "STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(render_service, "PUBLIC_BASE_URL", "")
    monkeypatch.setattr(image_asset_service, "STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(image_asset_service, "PUBLIC_BASE_URL", "")
    monkeypatch.setattr(image_asset_service, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(image_asset_service, "OPENAI_IMAGE_CARROSSEL_REQUEST_LIMIT", 2)
    monkeypatch.setattr(image_asset_service, "_count_openai_image_calls", lambda *args, **kwargs: 2)
    carrossel, first_slide = _fake_carrossel(template_id=43)
    second_slide = SimpleNamespace(
        id=2,
        carrossel_id=43,
        numero_slide=2,
        titulo="Segundo slide",
        texto_principal="Outro texto principal para validar fallback em render",
        texto_secundario=None,
        observacao_visual="Composição editorial com contraste diferente.",
        imagem_path=None,
        imagem_url=None,
        layout_config={},
    )
    carrossel.slides = [first_slide, second_slide]

    render_service.renderizar_carrossel_slides(FakeDb(), carrossel, template="clean_editorial")

    assert first_slide.layout_config["slide_asset_path"] != second_slide.layout_config["slide_asset_path"]
    assert (tmp_path / first_slide.layout_config["slide_asset_path"]).exists()
    assert (tmp_path / second_slide.layout_config["slide_asset_path"]).exists()
    assert (tmp_path / first_slide.imagem_path).exists()
    assert (tmp_path / second_slide.imagem_path).exists()


def _png_b64(color):
    buffer = BytesIO()
    Image.new("RGB", (1024, 1536), color).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def test_render_service_uses_openai_full_slide_for_each_slide(tmp_path, monkeypatch):
    monkeypatch.setattr(render_service, "STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(render_service, "PUBLIC_BASE_URL", "")
    monkeypatch.setattr(render_service, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(render_service, "OPENAI_IMAGE_MODEL", "gpt-image-test")
    monkeypatch.setattr(image_asset_service, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(render_service, "_image_limit_status", lambda *_args, **_kwargs: None)
    calls = []
    colors = [(220, 40, 60), (40, 80, 220)]

    class FakeImages:
        def generate(self, **kwargs):
            calls.append(kwargs)
            color = colors[len(calls) - 1]
            return SimpleNamespace(data=[SimpleNamespace(b64_json=_png_b64(color))])

    class FakeOpenAI:
        def __init__(self, api_key):
            self.api_key = api_key
            self.images = FakeImages()

    monkeypatch.setattr(render_service, "OpenAI", FakeOpenAI)
    carrossel, first_slide = _fake_carrossel(template_id=44)
    first_slide.titulo = "O começo: um projeto visionário"
    second_slide = SimpleNamespace(
        id=2,
        carrossel_id=44,
        numero_slide=2,
        titulo="Chegada ao Brasil",
        texto_principal="O Fusca desembarca e conquista o país com seu preço e resistência.",
        texto_secundario="",
        observacao_visual="Foto antiga do primeiro Fusca no porto ou nas ruas brasileiras dos anos 1950-60.",
        imagem_path=None,
        imagem_url=None,
        layout_config={},
    )
    carrossel.slides = [first_slide, second_slide]
    carrossel.publico_alvo = "Entusiastas de carros clássicos"
    carrossel.tom = "histórico e nostálgico"

    render_service.renderizar_carrossel_slides(FakeDb(), carrossel, template="clean_editorial")

    assert len(calls) == 2
    assert first_slide.layout_config["renderer"] == "openai_full_slide"
    assert second_slide.layout_config["renderer"] == "openai_full_slide"
    assert first_slide.layout_config["image_model"] == "gpt-image-test"
    assert "O começo: um projeto visionário" in first_slide.layout_config["image_prompt"]
    assert "Foto antiga do primeiro Fusca" in second_slide.layout_config["image_prompt"]
    assert first_slide.layout_config["slide_asset_path"] is None
    assert second_slide.layout_config["slide_asset_path"] is None
    first_render = tmp_path / first_slide.imagem_path
    second_render = tmp_path / second_slide.imagem_path
    assert first_render.exists()
    assert second_render.exists()
    assert first_render.read_bytes() != second_render.read_bytes()
    with Image.open(first_render) as image:
        assert image.size == (1080, 1350)


def test_render_service_falls_back_to_pillow_when_openai_full_slide_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(render_service, "STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(render_service, "PUBLIC_BASE_URL", "")
    monkeypatch.setattr(render_service, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(image_asset_service, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(render_service, "_image_limit_status", lambda *_args, **_kwargs: None)

    class FakeImages:
        def generate(self, **_kwargs):
            raise RuntimeError("image api unavailable")

    class FakeOpenAI:
        def __init__(self, api_key):
            self.api_key = api_key
            self.images = FakeImages()

    monkeypatch.setattr(render_service, "OpenAI", FakeOpenAI)
    carrossel, slide = _fake_carrossel(template_id=45)

    render_service.renderizar_carrossel_slides(FakeDb(), carrossel, template="clean_editorial")

    assert slide.layout_config["renderer"] == "pillow"
    assert slide.layout_config["fallback_reason"] == "erro_openai"
    assert slide.layout_config["fallback_error"] == "image api unavailable"
    assert (tmp_path / slide.imagem_path).exists()


def test_frontend_uses_only_global_background_asset_for_render():
    app_source = Path("frontend/src/App.jsx").read_text()
    panel_source = Path("frontend/src/components/ActionPanel.jsx").read_text()

    assert "asset.tipo === 'background'" in app_source
    assert "asset.tipo === 'background'" in panel_source


def test_openai_generation_creates_slides_and_updates_status(monkeypatch):
    payload = {
        "titulo": "Titulo refinado",
        "tema": "Produtividade",
        "publico_alvo": "Criadores independentes",
        "slides": [
            {
                "numero_slide": 2,
                "titulo": "Segundo passo",
                "texto_principal": "Organize o fluxo antes de automatizar.",
                "texto_secundario": None,
                "observacao_visual": "Mesa de trabalho limpa com elementos editoriais.",
            },
            {
                "numero_slide": 1,
                "titulo": "Comece simples",
                "texto_principal": "Automacao boa nasce de um processo claro.",
                "texto_secundario": "Menos atrito, mais consistencia.",
                "observacao_visual": "Abertura forte com contraste e espaco para titulo.",
            },
        ],
        "legenda": "Legenda pronta para revisao.",
        "hashtags": ["produtividade", "#conteudo digital", ""],
        "cta_final": "Salve para revisar depois.",
    }
    calls = {}

    class FakeResponses:
        def create(self, **kwargs):
            calls.update(kwargs)
            return SimpleNamespace(
                id="resp_123",
                output_text=json.dumps(payload),
                usage={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
            )

    class FakeOpenAI:
        def __init__(self, api_key):
            calls["api_key"] = api_key
            self.responses = FakeResponses()

    carrossel = SimpleNamespace(
        id=77,
        titulo="Titulo inicial",
        ideia_original="Ideia original para o carrossel",
        tema="Tema inicial",
        tom="pratico",
        publico_alvo="Profissionais solo",
        prompt_config={"observacoes_adicionais": "Use exemplos concretos."},
        quantidade_slides=2,
        slides=[],
        status="RASCUNHO",
        legenda=None,
        hashtags=None,
        ia_resultado=None,
    )
    db = FakeDb()

    monkeypatch.setattr(ai_service, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(ai_service, "OPENAI_MODEL", "gpt-test")
    monkeypatch.setattr(ai_service, "OpenAI", FakeOpenAI)
    monkeypatch.setattr(ai_service, "_verificar_limites", lambda *_args, **_kwargs: None)

    result = ai_service.gerar_carrossel_com_openai(db, carrossel)

    slides = [item for item in db.added if isinstance(item, CarrosselSlide)]
    assert calls["api_key"] == "test-key"
    assert calls["model"] == "gpt-test"
    assert calls["text"]["format"]["type"] == "json_schema"
    assert calls["text"]["format"]["schema"] == ai_service.CARROSSEL_RESPONSE_SCHEMA
    assert [slide.numero_slide for slide in slides] == [1, 2]
    assert result.status == STATUS_AGUARDANDO_APROVACAO
    assert result.ia_resultado["mock"] is False
    assert result.ia_resultado["provider"] == "openai"
    assert result.ia_resultado["usage"] == {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}
    assert result.hashtags == ["#produtividade", "#conteudodigital"]
