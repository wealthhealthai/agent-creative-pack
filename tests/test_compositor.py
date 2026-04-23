"""
test_compositor.py
==================
Tests that the compositor renders an HTML template and produces a valid PNG.
Runs without any API keys (all local).
"""

import os
import struct
import tempfile
import zlib
import sys

import pytest

# Ensure project root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from creative_pack.models import BrandKit, CopySet
from creative_pack.compositor import composite_ad, _image_to_base64_data_url


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_test_png(width: int = 200, height: int = 200) -> str:
    """Write a small solid-color PNG to a temp file and return its path."""
    try:
        from PIL import Image
        tmp = tempfile.mktemp(suffix=".png")
        img = Image.new("RGB", (width, height), (26, 63, 111))  # Helio blue
        img.save(tmp, "PNG")
        return tmp
    except ImportError:
        # Fallback: write a minimal valid PNG without PIL
        tmp = tempfile.mktemp(suffix=".png")
        _write_minimal_png(tmp, width, height)
        return tmp


def _write_minimal_png(path: str, width: int = 200, height: int = 200) -> None:
    """Write a minimal solid-color PNG using only stdlib."""
    def png_chunk(name: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(name + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + name + data + struct.pack(">I", crc)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = png_chunk(
        b"IHDR",
        struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0),
    )
    # Build raw scanlines: filter byte (0) + RGB pixels
    row = b"\x00" + b"\x1a\x3f\x6f" * width  # filter=None + Helio blue
    raw = row * height
    idat = png_chunk(b"IDAT", zlib.compress(raw, 9))
    iend = png_chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(sig + ihdr + idat + iend)


def _make_test_brand_kit() -> BrandKit:
    """Build a minimal BrandKit for testing."""
    return BrandKit(
        client_id="test_client",
        product_name="TestProduct",
        logo_url="",
        logo_position="top-right",
        primary_color="#1A3F6F",
        accent_color="#00B4D8",
        background_color="#FFFFFF",
        font_headline="Inter",
        font_headline_weight="700",
        font_body="Inter",
        font_body_weight="400",
        cta_style="rounded-pill",
        cta_color="#00B4D8",
        disclaimer_required=True,
        disclaimer_text="For investigational use only.",
        style_default="warm-clinical",
        image_style="lifestyle-emotional",
        fda_guardrails=True,
        guardrail_terms_blocked=["detects", "cures"],
        guardrail_terms_required=["consult your physician"],
        music_default=None,
    )


def _make_test_copy_set() -> CopySet:
    return CopySet(
        framework="PAS",
        headline="Know your liver health.",
        body="Simple. At-home. Trusted. Consult your physician before making health decisions.",
        cta="Order Now",
        disclaimer="For investigational use only.",
    )


def _is_valid_png(path: str) -> bool:
    """Check that a file starts with the PNG magic bytes."""
    try:
        with open(path, "rb") as f:
            magic = f.read(8)
        return magic == b"\x89PNG\r\n\x1a\n"
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_base64_encode_image():
    """_image_to_base64_data_url should return a data URL for a valid PNG."""
    img_path = _make_test_png(100, 100)
    try:
        data_url = _image_to_base64_data_url(img_path)
        assert data_url.startswith("data:image/"), f"Expected data URL, got: {data_url[:60]}"
        assert "base64," in data_url
    finally:
        if os.path.exists(img_path):
            os.remove(img_path)


def test_base64_encode_missing_file():
    """_image_to_base64_data_url should return empty string for missing file."""
    result = _image_to_base64_data_url("/nonexistent/path/image.png")
    assert result == ""


@pytest.mark.parametrize("template", ["lifestyle", "product_hero", "minimal"])
def test_composite_renders_png(template):
    """composite_ad should render a valid PNG for each template."""
    img_path = _make_test_png(300, 300)
    output_dir = tempfile.mkdtemp(prefix="cp_test_compositor_")
    brand_kit = _make_test_brand_kit()
    copy_set = _make_test_copy_set()

    try:
        result_path = composite_ad(
            image_path=img_path,
            copy_set=copy_set,
            brand_kit=brand_kit,
            platform="meta_static",
            template=template,
            output_dir=output_dir,
        )

        assert os.path.exists(result_path), f"Output file not found: {result_path}"
        file_size = os.path.getsize(result_path)
        assert file_size > 1000, f"Output PNG is suspiciously small: {file_size} bytes"
        assert _is_valid_png(result_path), f"Output file is not a valid PNG: {result_path}"

    finally:
        if os.path.exists(img_path):
            os.remove(img_path)


def test_composite_with_no_background_image():
    """composite_ad should succeed even when given an empty image path."""
    output_dir = tempfile.mkdtemp(prefix="cp_test_compositor_nobg_")
    brand_kit = _make_test_brand_kit()
    copy_set = _make_test_copy_set()

    result_path = composite_ad(
        image_path="",          # no background image
        copy_set=copy_set,
        brand_kit=brand_kit,
        platform="meta_static",
        template="minimal",
        output_dir=output_dir,
    )

    assert os.path.exists(result_path), f"Output file not found: {result_path}"
    assert _is_valid_png(result_path), "Output file is not a valid PNG"


def test_composite_output_dimensions():
    """The output PNG should have approximately the right dimensions."""
    img_path = _make_test_png(400, 400)
    output_dir = tempfile.mkdtemp(prefix="cp_test_compositor_dims_")
    brand_kit = _make_test_brand_kit()
    copy_set = _make_test_copy_set()

    try:
        result_path = composite_ad(
            image_path=img_path,
            copy_set=copy_set,
            brand_kit=brand_kit,
            platform="meta_static",    # 1080×1080
            template="lifestyle",
            output_dir=output_dir,
        )

        from PIL import Image
        with Image.open(result_path) as img:
            w, h = img.size
        assert w == 1080, f"Expected width 1080, got {w}"
        assert h == 1080, f"Expected height 1080, got {h}"

    except ImportError:
        pytest.skip("PIL not available for dimension check")
    finally:
        if os.path.exists(img_path):
            os.remove(img_path)
