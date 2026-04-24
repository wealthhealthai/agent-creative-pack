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


def test_mock_brief_headline_not_pre_truncated():
    """Expander now generates full-length copy. Truncation happens in compositor per-platform."""
    kit = get_test_brand_kit()
    brief = _mock_brief("test brief", kit, ["meta_static"])
    for v in brief.copy_variants:
        # Headlines should have content — length enforcement is compositor's job now
        assert v.headline, "Headline should not be empty"


def test_meta_story_body_not_cleared_by_expander():
    """meta_story_img body clearing now happens in compositor, not expander."""
    kit = get_test_brand_kit()
    brief = _mock_brief("test brief", kit, ["meta_story_img"])
    # Expander generates full copy — compositor handles per-platform limits
    # At least some variants should have non-empty body from the expander
    has_body = any(v.body for v in brief.copy_variants)
    assert has_body, "Expander should generate body copy (compositor clears for story platforms)"


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
