import json
import zipfile
from datetime import datetime
from io import BytesIO
from types import SimpleNamespace

import pytest

from app.services.export_service import export_carousel_to_zip


def _carousel(slides):
    return SimpleNamespace(
        id=123,
        titulo="Produto XYZ Launch",
        legenda="Conheça o novo produto...",
        hashtags=["#produto", "#launch"],
        created_at=datetime(2026, 5, 27, 10, 0, 0),
        slides=slides,
    )


def _slide(number, imagem_path):
    return SimpleNamespace(
        numero_slide=number,
        titulo=f"Slide {number} Title",
        texto_principal="Main text",
        texto_secundario="Secondary text",
        imagem_path=imagem_path,
    )


def test_export_carousel_to_zip_contains_slides_metadata_and_readme(tmp_path):
    first = tmp_path / "carrosseis/123/slides/slide-01.png"
    second = tmp_path / "carrosseis/123/slides/slide-02.png"
    first.parent.mkdir(parents=True)
    first.write_bytes(b"first-png")
    second.write_bytes(b"second-png")

    data = export_carousel_to_zip(
        None,
        _carousel([
            _slide(2, "carrosseis/123/slides/slide-02.png"),
            _slide(1, "carrosseis/123/slides/slide-01.png"),
        ]),
        tmp_path,
    )

    with zipfile.ZipFile(BytesIO(data)) as archive:
        assert archive.namelist() == ["slides/01.png", "slides/02.png", "metadata.json", "README.txt"]
        assert archive.read("slides/01.png") == b"first-png"
        metadata = json.loads(archive.read("metadata.json"))
        assert metadata["carousel_id"] == 123
        assert metadata["hashtags"] == ["#produto", "#launch"]
        assert metadata["total_slides"] == 2
        assert metadata["slides"][0]["number"] == 1
        readme = archive.read("README.txt").decode("utf-8")
        assert "arquivos exportados" in readme
        assert "Conheça o novo produto..." in readme


def test_export_carousel_to_zip_rejects_missing_rendered_image(tmp_path):
    with pytest.raises(ValueError) as exc_info:
        export_carousel_to_zip(None, _carousel([_slide(1, None)]), tmp_path)

    assert str(exc_info.value) == "Um ou mais slides não têm imagem renderizada."
