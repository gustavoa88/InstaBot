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


def test_render_service_rejects_selected_asset_in_openai_only_mode(tmp_path, monkeypatch):
    monkeypatch.setattr(render_service, "STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(render_service, "PUBLIC_BASE_URL", "")
    carrossel, _slide = _fake_carrossel()
    asset = SimpleNamespace(id=99, asset_path="carrosseis/10/assets/asset-test.png")

    with pytest.raises(HTTPException) as exc_info:
        render_service.renderizar_carrossel_slides(
            FakeDb(),
            carrossel,
            template="clean_editorial",
            brand_name="InstaBot",
            primary_color="#336699",
            asset=asset,
            api_key="test-key",
        )

    assert exc_info.value.status_code == 409
    assert "asset selecionado" in exc_info.value.detail

def test_render_service_requires_openai_key_in_openai_only_mode(tmp_path, monkeypatch):
    monkeypatch.setattr(render_service, "STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(render_service, "PUBLIC_BASE_URL", "")
    carrossel, _slide = _fake_carrossel(template_id=18)

    with pytest.raises(HTTPException) as exc_info:
        render_service.renderizar_carrossel_slides(FakeDb(), carrossel, template="clean_editorial")

    assert exc_info.value.status_code == 409
    assert "OPENAI_API_KEY" in exc_info.value.detail

@pytest.mark.parametrize("template", ["clean_editorial", "bold_contrast", "soft_brand"])
def test_render_service_supports_visual_templates(tmp_path, monkeypatch, template):
    monkeypatch.setattr(render_service, "STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(render_service, "PUBLIC_BASE_URL", "")
    carrossel, _slide = _fake_carrossel(template_id=20)

    with pytest.raises(HTTPException) as exc_info:
        render_service.renderizar_carrossel_slides(FakeDb(), carrossel, template=template)

    assert exc_info.value.status_code == 409
    assert "OPENAI_API_KEY" in exc_info.value.detail

def test_render_service_does_not_generate_local_slide_assets_without_openai(tmp_path, monkeypatch):
    monkeypatch.setattr(render_service, "STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(render_service, "PUBLIC_BASE_URL", "")
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

    with pytest.raises(HTTPException) as exc_info:
        render_service.renderizar_carrossel_slides(db, carrossel, template="clean_editorial")

    assert exc_info.value.status_code == 409
    assert not [item for item in db.added if getattr(item, "tipo", None) == "slide_background"]

def test_render_service_rejects_asset_instead_of_using_pillow_renderer(tmp_path, monkeypatch):
    monkeypatch.setattr(render_service, "STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(render_service, "PUBLIC_BASE_URL", "")
    carrossel, _slide = _fake_carrossel(template_id=41)
    asset = SimpleNamespace(id=501, asset_path="carrosseis/41/assets/slide-blue.png")

    with pytest.raises(HTTPException) as exc_info:
        render_service.renderizar_carrossel_slides(FakeDb(), carrossel, template="clean_editorial", asset=asset, api_key="test-key")

    assert exc_info.value.status_code == 409
    assert "OpenAI-only" in exc_info.value.detail

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


def test_render_service_aborts_when_openai_image_limit_is_reached(tmp_path, monkeypatch):
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

    with pytest.raises(HTTPException) as exc_info:
        render_service.renderizar_carrossel_slides(FakeDb(), carrossel, template="clean_editorial")

    assert exc_info.value.status_code == 429
    assert "Limite de geração de imagem da OpenAI atingido" in exc_info.value.detail
    assert first_slide.imagem_path is None
    assert second_slide.imagem_path is None
    assert not (tmp_path / "carrosseis/43/slides").exists()


def _png_b64(color):
    buffer = BytesIO()
    Image.new("RGB", (1024, 1536), color).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def test_openai_full_slide_save_preserves_provider_bytes(tmp_path):
    buffer = BytesIO()
    Image.new("RGB", (1024, 1536), (30, 60, 90)).save(buffer, format="PNG")
    output = tmp_path / "openai-slide.png"

    render_service._save_full_slide_bytes(buffer.getvalue(), output)

    assert output.read_bytes() == buffer.getvalue()
    with Image.open(output) as rendered:
        assert rendered.size == (1024, 1536)

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

    render_service.renderizar_carrossel_slides(FakeDb(), carrossel, template="clean_editorial", usuario=SimpleNamespace(is_admin=True))

    assert len(calls) == 2
    assert first_slide.layout_config["renderer"] == "openai_full_slide"
    assert second_slide.layout_config["renderer"] == "openai_full_slide"
    assert first_slide.layout_config["image_model"] == "gpt-image-test"
    assert "O começo: um projeto visionário" in first_slide.layout_config["image_prompt"]
    assert "Foto antiga do primeiro Fusca" in second_slide.layout_config["image_prompt"]
    assert first_slide.layout_config["slide_asset_path"] is None
    assert second_slide.layout_config["slide_asset_path"] is None
    prompt = first_slide.layout_config["image_prompt"]
    assert "titulo:" in prompt
    assert "texto_principal:" in prompt
    assert "texto_secundario:" in prompt
    assert "observacao_visual:" in prompt
    assert "Renderize titulo, texto_principal e texto_secundario" in prompt
    assert "do not include text" not in prompt.lower()
    first_render = tmp_path / first_slide.imagem_path
    second_render = tmp_path / second_slide.imagem_path
    assert first_render.exists()
    assert second_render.exists()
    assert first_render.read_bytes() != second_render.read_bytes()
    with Image.open(first_render) as image:
        assert image.size == (1024, 1536)


def test_render_service_aborts_without_partial_updates_when_openai_key_is_invalid(tmp_path, monkeypatch):
    monkeypatch.setattr(render_service, "STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(render_service, "PUBLIC_BASE_URL", "")
    monkeypatch.setattr(render_service, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(image_asset_service, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(render_service, "_image_limit_status", lambda *_args, **_kwargs: None)

    class FakeOpenAIError(Exception):
        status_code = 401

    class FakeImages:
        def __init__(self):
            self.calls = 0

        def generate(self, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return SimpleNamespace(data=[SimpleNamespace(b64_json=_png_b64((30, 120, 200)))])
            raise FakeOpenAIError("Incorrect API key provided: sk-secret")

    class FakeOpenAI:
        images = FakeImages()

        def __init__(self, api_key):
            self.api_key = api_key

    monkeypatch.setattr(render_service, "OpenAI", FakeOpenAI)
    carrossel, first_slide = _fake_carrossel(template_id=45)
    second_slide = SimpleNamespace(
        id=2,
        carrossel_id=45,
        numero_slide=2,
        titulo="Segundo slide",
        texto_principal="Texto que não deve ser parcialmente renderizado.",
        texto_secundario="",
        observacao_visual="Cena editorial de validação.",
        imagem_path="carrosseis/45/slides/slide-02-old.png",
        imagem_url="/storage/carrosseis/45/slides/slide-02-old.png",
        layout_config={"renderer": "old"},
    )
    first_slide.imagem_path = "carrosseis/45/slides/slide-01-old.png"
    first_slide.imagem_url = "/storage/carrosseis/45/slides/slide-01-old.png"
    first_slide.layout_config = {"renderer": "old"}
    carrossel.slides = [first_slide, second_slide]

    with pytest.raises(HTTPException) as exc_info:
        render_service.renderizar_carrossel_slides(FakeDb(), carrossel, template="clean_editorial")

    assert exc_info.value.status_code == 401
    assert "Chave OpenAI inválida ou expirada" in exc_info.value.detail
    assert "Incorrect API key provided" in exc_info.value.detail
    assert "sk-secret" not in exc_info.value.detail
    assert first_slide.layout_config == {"renderer": "old"}
    assert second_slide.layout_config == {"renderer": "old"}
    assert first_slide.imagem_path == "carrosseis/45/slides/slide-01-old.png"
    assert not list((tmp_path / "carrosseis/45/slides").glob("*.tmp.png"))


def test_openai_429_error_detail_is_returned_in_banner_message(tmp_path, monkeypatch):
    monkeypatch.setattr(render_service, "STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(render_service, "PUBLIC_BASE_URL", "")
    monkeypatch.setattr(render_service, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(image_asset_service, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(render_service, "_image_limit_status", lambda *_args, **_kwargs: None)

    class FakeOpenAIRateLimit(Exception):
        status_code = 429

    class FakeImages:
        def generate(self, **_kwargs):
            raise FakeOpenAIRateLimit("Rate limit reached for gpt-image-1-mini in organization org_test. Please try again in 20s.")

    class FakeOpenAI:
        def __init__(self, api_key):
            self.api_key = api_key
            self.images = FakeImages()

    monkeypatch.setattr(render_service, "OpenAI", FakeOpenAI)
    carrossel, _slide = _fake_carrossel(template_id=47)

    with pytest.raises(HTTPException) as exc_info:
        render_service.renderizar_carrossel_slides(FakeDb(), carrossel, template="clean_editorial")

    assert exc_info.value.status_code == 429
    assert "Limite de geração de imagem da OpenAI atingido" in exc_info.value.detail
    assert "Rate limit reached for gpt-image-1-mini" in exc_info.value.detail


def test_render_service_retries_transient_openai_full_slide_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(render_service, "STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(render_service, "PUBLIC_BASE_URL", "")
    monkeypatch.setattr(render_service, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(image_asset_service, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(render_service, "_image_limit_status", lambda *_args, **_kwargs: None)
    calls = []

    class FakeImages:
        def generate(self, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                raise RuntimeError("temporary outage")
            return SimpleNamespace(data=[SimpleNamespace(b64_json=_png_b64((80, 170, 110)))])

    class FakeOpenAI:
        def __init__(self, api_key):
            self.api_key = api_key
            self.images = FakeImages()

    monkeypatch.setattr(render_service, "OpenAI", FakeOpenAI)
    carrossel, slide = _fake_carrossel(template_id=46)

    render_service.renderizar_carrossel_slides(FakeDb(), carrossel, template="clean_editorial", usuario=SimpleNamespace(is_admin=True))

    assert len(calls) == 2
    assert slide.layout_config["renderer"] == "openai_full_slide"
    assert (tmp_path / slide.imagem_path).exists()


def test_image_limits_are_per_user_and_admin_has_higher_daily_limit(monkeypatch):
    carrossel, _slide = _fake_carrossel(template_id=91)
    carrossel.usuario_id = 10
    normal_user = SimpleNamespace(id=10, is_admin=False)
    admin_user = SimpleNamespace(id=10, is_admin=True)
    seen_usuario_ids = []

    monkeypatch.setattr(image_asset_service, "OPENAI_IMAGE_DAILY_REQUEST_LIMIT", 1)
    monkeypatch.setattr(image_asset_service, "OPENAI_IMAGE_ADMIN_DAILY_REQUEST_LIMIT", 100)
    monkeypatch.setattr(image_asset_service, "OPENAI_IMAGE_CARROSSEL_REQUEST_LIMIT", 7)

    def fake_count(*_args, **kwargs):
        seen_usuario_ids.append(kwargs.get("usuario_id"))
        return 1 if kwargs.get("desde") is not None else 0

    monkeypatch.setattr(image_asset_service, "_count_openai_image_calls", fake_count)

    normal_status = image_asset_service._image_limit_status(FakeDb(), carrossel, usuario=normal_user)
    admin_status = image_asset_service._image_limit_status(FakeDb(), carrossel, usuario=admin_user)

    assert normal_status == {"escopo": "diário", "limite": 1, "chamadas": 1}
    assert admin_status is None
    assert seen_usuario_ids == [normal_user.id]


def test_text_limits_are_per_user_and_admin_has_higher_daily_limit(monkeypatch):
    carrossel, _slide = _fake_carrossel(template_id=92)
    carrossel.usuario_id = 11
    normal_user = SimpleNamespace(id=11, is_admin=False)
    admin_user = SimpleNamespace(id=11, is_admin=True)
    seen_usuario_ids = []

    monkeypatch.setattr(ai_service, "OPENAI_DAILY_REQUEST_LIMIT", 1)
    monkeypatch.setattr(ai_service, "OPENAI_ADMIN_DAILY_REQUEST_LIMIT", 100)
    monkeypatch.setattr(ai_service, "OPENAI_CARROSSEL_REQUEST_LIMIT", 3)

    def fake_count(*_args, **kwargs):
        seen_usuario_ids.append(kwargs.get("usuario_id"))
        return 1 if kwargs.get("desde") is not None else 0

    monkeypatch.setattr(ai_service, "_contar_chamadas_openai", fake_count)

    with pytest.raises(HTTPException) as exc_info:
        ai_service._verificar_limites(FakeDb(), carrossel, usuario=normal_user)

    assert exc_info.value.status_code == 429
    assert "(1/1)" in exc_info.value.detail
    ai_service._verificar_limites(FakeDb(), carrossel, usuario=admin_user)
    assert seen_usuario_ids[:2] == [normal_user.id, admin_user.id]


def test_image_limits_are_temporarily_disabled_for_admin(monkeypatch):
    carrossel, _slide = _fake_carrossel(template_id=93)
    admin_user = SimpleNamespace(id=12, is_admin=True)

    monkeypatch.setattr(image_asset_service, "OPENAI_IMAGE_DAILY_REQUEST_LIMIT", 1)
    monkeypatch.setattr(image_asset_service, "OPENAI_IMAGE_ADMIN_DAILY_REQUEST_LIMIT", 100)
    monkeypatch.setattr(image_asset_service, "OPENAI_IMAGE_CARROSSEL_REQUEST_LIMIT", 7)
    monkeypatch.setattr(image_asset_service, "_count_openai_image_calls", lambda *_args, **_kwargs: 999)

    assert image_asset_service._image_limit_status(FakeDb(), carrossel, usuario=admin_user) is None

def test_frontend_uses_only_global_background_asset_for_render():
    app_source = Path("frontend/src/App.jsx").read_text()
    panel_source = Path("frontend/src/components/ActionPanel.jsx").read_text()

    assert "asset.tipo === 'background'" in app_source
    assert "asset.tipo === 'background'" in panel_source


def test_openai_text_generation_401_returns_clear_sanitized_error(monkeypatch):
    class FakeOpenAIAuthError(Exception):
        status_code = 401

    class FakeResponses:
        def create(self, **_kwargs):
            raise FakeOpenAIAuthError("Incorrect API key provided: sk-secret")

    class FakeOpenAI:
        def __init__(self, api_key):
            self.api_key = api_key
            self.responses = FakeResponses()

    carrossel = SimpleNamespace(
        id=81,
        titulo="Titulo inicial",
        ideia_original="Ideia original para o carrossel",
        tema="Tema inicial",
        tom="pratico",
        publico_alvo="Profissionais solo",
        prompt_config={},
        quantidade_slides=2,
        slides=[],
        status="RASCUNHO",
    )

    monkeypatch.setattr(ai_service, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(ai_service, "OpenAI", FakeOpenAI)
    monkeypatch.setattr(ai_service, "_verificar_limites", lambda *_args, **_kwargs: None)

    with pytest.raises(HTTPException) as exc_info:
        ai_service.gerar_carrossel_com_openai(FakeDb(), carrossel)

    assert exc_info.value.status_code == 401
    assert "Chave OpenAI inválida ou expirada" in exc_info.value.detail
    assert "Incorrect API key provided" in exc_info.value.detail
    assert "sk-secret" not in exc_info.value.detail


def test_openai_text_generation_429_returns_openai_detail(monkeypatch):
    class FakeOpenAIRateLimit(Exception):
        status_code = 429

    class FakeResponses:
        def create(self, **_kwargs):
            raise FakeOpenAIRateLimit("Rate limit reached for gpt-5-mini. Try again in 10s.")

    class FakeOpenAI:
        def __init__(self, api_key):
            self.api_key = api_key
            self.responses = FakeResponses()

    carrossel = SimpleNamespace(
        id=82,
        titulo="Titulo inicial",
        ideia_original="Ideia original para o carrossel",
        tema="Tema inicial",
        tom="pratico",
        publico_alvo="Profissionais solo",
        prompt_config={},
        quantidade_slides=2,
        slides=[],
        status="RASCUNHO",
    )

    monkeypatch.setattr(ai_service, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(ai_service, "OpenAI", FakeOpenAI)
    monkeypatch.setattr(ai_service, "_verificar_limites", lambda *_args, **_kwargs: None)

    with pytest.raises(HTTPException) as exc_info:
        ai_service.gerar_carrossel_com_openai(FakeDb(), carrossel)

    assert exc_info.value.status_code == 429
    assert "Limite de geração textual da OpenAI atingido" in exc_info.value.detail
    assert "Rate limit reached for gpt-5-mini" in exc_info.value.detail


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
