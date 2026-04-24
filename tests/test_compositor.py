"""Tests for the HTML/CSS compositor — verifies Playwright renders real PNGs."""
import os
import tempfile
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from creative_pack.models import CopySet, BrandKit
from creative_pack.compositor import composite_ad, _truncate_copy_for_platform
from creative_pack.config import load_brand_kit


def get_test_brand_kit() -> BrandKit:
    data = load_brand_kit("helio_livertrace")
    return BrandKit.from_dict(data)


def make_test_image(path: str, w: int = 1080, h: int = 1080) -> str:
    """Create a solid-color test image."""
    try:
        from PIL import Image
        img = Image.new("RGB", (w, h), color=(26, 63, 111))
        img.save(path)
        return path
    except ImportError:
        pytest.skip("Pillow not installed")


def test_compositor_renders_png():
    """Compositor should render a valid PNG file at correct dimensions."""
    kit = get_test_brand_kit()
    copy_set = CopySet(
        framework="PAS",
        headline="Know Your Liver Risk",
        body="Get answers at home in minutes.",
        cta="Order Now →",
        disclaimer=kit.disclaimer_text,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        bg_image = os.path.join(tmpdir, "bg.png")
        make_test_image(bg_image)

        out_path = composite_ad(
            image_path=bg_image,
            copy_set=copy_set,
            brand_kit=kit,
            platform="meta_static",
            template="lifestyle",
            output_dir=tmpdir,
        )

        assert os.path.exists(out_path), f"Output file not found: {out_path}"
        assert out_path.endswith(".png"), "Output should be PNG"
        assert os.path.getsize(out_path) > 1000, "Output file too small to be a real image"

        # Verify dimensions
        from PIL import Image
        img = Image.open(out_path)
        assert img.width == 1080, f"Expected width 1080, got {img.width}"
        assert img.height == 1080, f"Expected height 1080, got {img.height}"


def test_compositor_story_format():
    """Test 9:16 story format renders at correct size."""
    kit = get_test_brand_kit()
    copy_set = CopySet(
        framework="AIDA",
        headline="Your Liver Matters",
        body="",  # no body for story
        cta="Learn More",
        disclaimer=None,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        bg_image = os.path.join(tmpdir, "bg.png")
        make_test_image(bg_image, 1080, 1920)

        out_path = composite_ad(
            image_path=bg_image,
            copy_set=copy_set,
            brand_kit=kit,
            platform="meta_story_img",
            template="lifestyle",
            output_dir=tmpdir,
        )

        assert os.path.exists(out_path)
        from PIL import Image
        img = Image.open(out_path)
        assert img.width == 1080
        assert img.height == 1920


def test_compositor_minimal_template():
    """Minimal template should also render without error."""
    kit = get_test_brand_kit()
    copy_set = CopySet(
        framework="emotional",
        headline="For the people paying attention.",
        body="Know your liver.",
        cta="Learn More",
        disclaimer=None,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        bg_image = os.path.join(tmpdir, "bg.png")
        make_test_image(bg_image)

        out_path = composite_ad(
            image_path=bg_image,
            copy_set=copy_set,
            brand_kit=kit,
            platform="meta_static",
            template="minimal",
            output_dir=tmpdir,
        )

        assert os.path.exists(out_path)
        assert os.path.getsize(out_path) > 1000


def test_per_platform_truncation():
    """Compositor truncates headline/body to platform-specific limits."""
    long_copy = CopySet(
        framework="PAS",
        headline="This headline is way too long and exceeds forty characters easily",
        body="This is a long body that exceeds the 125-char limit for meta " * 3,
        cta="Order Now",
        disclaimer=None,
    )
    # meta_static: headline≤40, body≤125
    truncated = _truncate_copy_for_platform(long_copy, "meta_static")
    assert len(truncated.headline) <= 40, f"Headline not truncated: {len(truncated.headline)}"
    assert len(truncated.body) <= 125, f"Body not truncated: {len(truncated.body)}"

    # meta_story_img: body=0
    story_copy = _truncate_copy_for_platform(long_copy, "meta_story_img")
    assert story_copy.body == "", "Story body should be empty"

    # google_display: headline≤30
    display_copy = _truncate_copy_for_platform(long_copy, "google_display")
    assert len(display_copy.headline) <= 30, f"GD headline not truncated: {len(display_copy.headline)}"


def test_compositor_google_display():
    """Landscape 1200×628 format."""
    kit = get_test_brand_kit()
    copy_set = CopySet(
        framework="PAS",
        headline="Liver Health, Simplified",
        body="At-home screening, trusted results.",
        cta="Get Started",
        disclaimer=kit.disclaimer_text,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        bg_image = os.path.join(tmpdir, "bg.png")
        make_test_image(bg_image, 1200, 628)

        out_path = composite_ad(
            image_path=bg_image,
            copy_set=copy_set,
            brand_kit=kit,
            platform="google_display",
            template="product_hero",
            output_dir=tmpdir,
        )

        assert os.path.exists(out_path)
        from PIL import Image
        img = Image.open(out_path)
        assert img.width == 1200
        assert img.height == 628
