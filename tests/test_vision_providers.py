"""
Offline tests for the multi-provider vision layer (no API calls, no keys used —
dummy keys construct clients but nothing is sent).
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _png(w, h):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (w, h), "white").save(buf, format="PNG")
    return buf.getvalue()


# ---- model-dependent resolution (the 1568 -> 2576 upgrade) -------------------

def test_anthropic_max_side_by_model():
    from providers.vision import AnthropicVisionProvider

    old = AnthropicVisionProvider(api_key="dummy", model="claude-sonnet-4-6")
    new = AnthropicVisionProvider(api_key="dummy", model="claude-sonnet-5")
    opus = AnthropicVisionProvider(api_key="dummy", model="claude-opus-4-8")
    assert old.max_side == 1568
    assert new.max_side == 2576 and opus.max_side == 2576


def test_prepare_respects_instance_max_side():
    from providers.vision import AnthropicVisionProvider
    from PIL import Image

    p = AnthropicVisionProvider(api_key="dummy", model="claude-sonnet-5")
    data, mt = p._prepare(_png(6000, 3000), "image/png")
    img = Image.open(io.BytesIO(data))
    assert max(img.size) == p.max_side == 2576
    assert mt == "image/png"


def test_downscale_no_upscale():
    from providers.vision import _downscale
    from PIL import Image

    data, _ = _downscale(_png(400, 300), 2048)
    img = Image.open(io.BytesIO(data))
    assert img.size == (400, 300)  # small images pass through untouched


# ---- ABC contract -------------------------------------------------------------

def test_abstract_contract_enforced():
    from providers.vision import VisionProvider

    class Incomplete(VisionProvider):  # missing extract/extract_multi
        def describe(self, *a, **k): ...
        @property
        def model_name(self): return "x"

    with pytest.raises(TypeError):
        Incomplete()  # provider swap must fail at the interface, not mid-run


# ---- routing factory ------------------------------------------------------------

def test_routing_default_and_per_class(monkeypatch):
    import providers.vision as vision

    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy")
    monkeypatch.setenv("VISION_MODEL", "claude-sonnet-5")
    monkeypatch.setenv("VISION_PROVIDER", "anthropic")
    monkeypatch.setenv("VISION_ROUTES", "electrical:anthropic, pid:anthropic")
    vision._PROVIDER_CACHE.clear()

    p_default = vision.get_vision_provider()
    p_routed = vision.get_vision_provider("electrical")
    p_unrouted = vision.get_vision_provider("hydraulic_schematic")
    assert type(p_default).__name__ == "AnthropicVisionProvider"
    assert p_routed is p_default  # cached instance reused per vendor
    assert p_unrouted is p_default  # unrouted class -> default vendor
    vision._PROVIDER_CACHE.clear()


def test_routing_unknown_vendor_fails_loud(monkeypatch):
    import providers.vision as vision

    monkeypatch.setenv("VISION_PROVIDER", "notavendor")
    vision._PROVIDER_CACHE.clear()
    with pytest.raises(NotImplementedError):
        vision.get_vision_provider()
    vision._PROVIDER_CACHE.clear()


# ---- Gemini schema cleaning -----------------------------------------------------

def test_gemini_schema_strips_unsupported_keys():
    gemini = pytest.importorskip("google.genai", reason="google-genai not installed")
    from providers.vision import GeminiVisionProvider

    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "slices": {
                "type": "array",
                "items": {"type": "object", "additionalProperties": False,
                          "properties": {"label": {"type": "string"}},
                          "required": ["label"]},
            }
        },
        "required": ["slices"],
    }
    cleaned = GeminiVisionProvider._clean_schema(schema)
    assert "additionalProperties" not in cleaned
    assert "additionalProperties" not in cleaned["properties"]["slices"]["items"]
    assert cleaned["required"] == ["slices"]  # supported keys survive


# ---- bench manifest sanity ------------------------------------------------------

def test_bench_manifest_parses_and_covers_categories():
    import json

    m = json.loads((Path(__file__).parent / "vision_bench_manifest.json").read_text())
    cats = m["categories"]
    assert len(cats) == 10
    for c in cats:
        assert c["protocol"].split(":")[0] in ("hydraulic", "electrical", "describe")
        assert len(c["sheets"]) == 2
