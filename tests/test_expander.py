"""
test_expander.py
================
Tests the brief expander in mock mode (no ANTHROPIC_API_KEY required).
Verifies structure, variant count, and character limit enforcement.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from creative_pack.models import BrandKit, CopySet, CreativeBrief
from creative_pack.expander import expand_brief, _enforce_char_limits, _mock_brief


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_brand_kit(fda: bool = True, image_style: str = "lifestyle-emotional") -> BrandKit:
    return BrandKit(
        client_id="helio_livertrace",
        product_name="LiverTrace",
        logo_url="https://example.com/logo.png",
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
        disclaimer_text="For investigational use only. Not for clinical diagnosis.",
        style_default="warm-clinical",
        image_style=image_style,
        fda_guardrails=fda,
        guardrail_terms_blocked=["detects", "prevents", "cures", "treats"],
        guardrail_terms_required=["consult your physician"],
        music_default=None,
    )


# ---------------------------------------------------------------------------
# Mock expander tests (no API key required)
# ---------------------------------------------------------------------------

def test_mock_brief_returns_creative_brief():
    """expand_brief (mock) returns a CreativeBrief instance."""
    # Ensure no API key is set
    os.environ.pop("ANTHROPIC_API_KEY", None)

    brand_kit = make_brand_kit()
    result = expand_brief(
        brief="LiverTrace DTC, warm hopeful, adults 40+",
        brand_kit=brand_kit,
        platforms=["meta_static"],
    )

    assert isinstance(result, CreativeBrief), f"Expected CreativeBrief, got {type(result)}"


def test_mock_brief_has_three_variants():
    """expand_brief (mock) always returns exactly 3 copy variants."""
    os.environ.pop("ANTHROPIC_API_KEY", None)

    brand_kit = make_brand_kit()
    result = expand_brief(
        brief="Test brief",
        brand_kit=brand_kit,
        platforms=["meta_static"],
    )

    assert len(result.copy_variants) == 3, (
        f"Expected 3 copy variants, got {len(result.copy_variants)}"
    )


def test_mock_brief_frameworks():
    """The three variants should use PAS, AIDA, and emotional frameworks."""
    os.environ.pop("ANTHROPIC_API_KEY", None)

    brand_kit = make_brand_kit()
    result = expand_brief(
        brief="Test brief",
        brand_kit=brand_kit,
        platforms=["meta_static"],
    )

    frameworks = {cv.framework for cv in result.copy_variants}
    assert "PAS" in frameworks, f"Missing PAS framework. Got: {frameworks}"
    assert "AIDA" in frameworks, f"Missing AIDA framework. Got: {frameworks}"
    assert "emotional" in frameworks, f"Missing emotional framework. Got: {frameworks}"


def test_mock_brief_copy_sets_are_copyset_instances():
    """Each copy variant must be a CopySet instance."""
    os.environ.pop("ANTHROPIC_API_KEY", None)

    brand_kit = make_brand_kit()
    result = expand_brief(
        brief="Test brief",
        brand_kit=brand_kit,
        platforms=["meta_static"],
    )

    for cv in result.copy_variants:
        assert isinstance(cv, CopySet), f"Expected CopySet, got {type(cv)}"
        assert cv.headline, "Headline must not be empty"
        assert cv.cta, "CTA must not be empty"


def test_mock_brief_disclaimer_injected_when_fda():
    """When fda_guardrails=True, all variants must have a disclaimer."""
    os.environ.pop("ANTHROPIC_API_KEY", None)

    brand_kit = make_brand_kit(fda=True)
    result = expand_brief(
        brief="Test",
        brand_kit=brand_kit,
        platforms=["meta_static"],
    )

    for cv in result.copy_variants:
        assert cv.disclaimer, (
            f"Expected disclaimer for FDA brand kit, got None for {cv.framework}"
        )


def test_mock_brief_platforms_stored():
    """The resulting CreativeBrief should store the requested platforms."""
    os.environ.pop("ANTHROPIC_API_KEY", None)

    brand_kit = make_brand_kit()
    platforms = ["meta_static", "google_display"]
    result = expand_brief(
        brief="Test",
        brand_kit=brand_kit,
        platforms=platforms,
    )

    assert result.platforms == platforms


# ---------------------------------------------------------------------------
# Character limit enforcement
# ---------------------------------------------------------------------------

def test_enforce_char_limits_headline_truncated():
    """Headlines over platform limit must be truncated with ellipsis."""
    long_headline = "A" * 100  # Way over meta_static limit of 40
    cs = CopySet(
        framework="PAS",
        headline=long_headline,
        body="Body text here",
        cta="Order Now",
        disclaimer=None,
    )
    result = _enforce_char_limits(cs, "meta_static")
    assert len(result.headline) <= 40, (
        f"Headline should be ≤40 chars, got {len(result.headline)}"
    )
    assert result.headline.endswith("…"), "Truncated headline should end with ellipsis"


def test_enforce_char_limits_body_truncated():
    """Body text over platform limit must be truncated."""
    long_body = "B" * 500  # Over meta_static limit of 125
    cs = CopySet(
        framework="AIDA",
        headline="Short headline",
        body=long_body,
        cta="Order",
        disclaimer=None,
    )
    result = _enforce_char_limits(cs, "meta_static")
    assert len(result.body) <= 125, (
        f"Body should be ≤125 chars, got {len(result.body)}"
    )
    assert result.body.endswith("…"), "Truncated body should end with ellipsis"


def test_enforce_char_limits_no_truncation_within_limit():
    """Text within limits should not be modified."""
    headline = "Short headline"
    body = "Short body."
    cs = CopySet(
        framework="emotional",
        headline=headline,
        body=body,
        cta="Learn More",
        disclaimer=None,
    )
    result = _enforce_char_limits(cs, "meta_static")
    assert result.headline == headline, "Headline should be unchanged"
    assert result.body == body, "Body should be unchanged"


def test_enforce_char_limits_google_display():
    """Google Display has a 30-char headline limit."""
    cs = CopySet(
        framework="PAS",
        headline="This headline is longer than thirty chars",
        body="Short body",
        cta="Click",
        disclaimer=None,
    )
    result = _enforce_char_limits(cs, "google_display")
    assert len(result.headline) <= 30, (
        f"Google Display headline should be ≤30 chars, got {len(result.headline)}"
    )


def test_mock_brief_body_within_limit():
    """Mock brief bodies must respect platform character limits."""
    os.environ.pop("ANTHROPIC_API_KEY", None)

    brand_kit = make_brand_kit()
    result = expand_brief(
        brief="Test brief",
        brand_kit=brand_kit,
        platforms=["meta_static"],
    )

    for cv in result.copy_variants:
        if cv.body:
            assert len(cv.body) <= 125, (
                f"Body for {cv.framework} exceeds 125 chars: {len(cv.body)}"
            )
