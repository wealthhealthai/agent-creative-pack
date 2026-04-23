"""Tests for brief expander — runs without any API keys."""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from creative_pack.models import BrandKit
from creative_pack.expander import expand_brief, _mock_brief
from creative_pack.config import load_brand_kit


def get_test_brand_kit() -> BrandKit:
    data = load_brand_kit("helio_livertrace")
    return BrandKit.from_dict(data)


def test_mock_brief_returns_three_variants():
    kit = get_test_brand_kit()
    brief = _mock_brief("test brief", kit, ["meta_static"])
    assert len(brief.copy_variants) == 3


def test_mock_brief_frameworks():
    kit = get_test_brand_kit()
    brief = _mock_brief("test brief", kit, ["meta_static"])
    frameworks = {v.framework for v in brief.copy_variants}
    assert "PAS" in frameworks
    assert "AIDA" in frameworks
    assert "emotional" in frameworks


def test_mock_brief_has_content():
    kit = get_test_brand_kit()
    brief = _mock_brief("test brief", kit, ["meta_static"])
    for v in brief.copy_variants:
        assert v.headline, "Headline should not be empty"
        assert v.cta, "CTA should not be empty"


def test_mock_brief_disclaimer_injected():
    kit = get_test_brand_kit()
    assert kit.disclaimer_required, "LiverTrace should require disclaimer"
    brief = _mock_brief("test brief", kit, ["meta_static"])
    for v in brief.copy_variants:
        assert v.disclaimer == kit.disclaimer_text


def test_mock_brief_headline_truncated_for_meta():
    kit = get_test_brand_kit()
    brief = _mock_brief("test brief", kit, ["meta_static"])
    for v in brief.copy_variants:
        assert len(v.headline) <= 40, f"Headline too long for meta_static: {v.headline}"


def test_meta_story_body_empty():
    """meta_story_img has no body text (char limit = 0)."""
    kit = get_test_brand_kit()
    brief = _mock_brief("test brief", kit, ["meta_story_img"])
    for v in brief.copy_variants:
        assert v.body == "", f"Body should be empty for meta_story_img, got: {v.body}"


def test_expand_brief_falls_back_to_mock_without_key(monkeypatch):
    """expand_brief should use mock when ANTHROPIC_API_KEY is not set."""
    monkeypatch.setattr("creative_pack.expander.ANTHROPIC_API_KEY", "")
    kit = get_test_brand_kit()
    brief = expand_brief("test brief", kit, ["meta_static"])
    assert len(brief.copy_variants) == 3
    assert brief.product_name


def test_creative_brief_has_image_direction():
    kit = get_test_brand_kit()
    brief = _mock_brief("test brief", kit, ["meta_static"])
    assert brief.image_direction, "Image direction should be populated"
    # Should follow lifestyle-emotional pattern
    assert any(kw in brief.image_direction.lower() for kw in ["light", "home", "warm", "relief"])
