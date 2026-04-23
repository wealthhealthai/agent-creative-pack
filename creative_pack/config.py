"""
Configuration for the Creative Capability Pack.
Platform specs, directory paths, and environment variable loading.
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Root paths
# ---------------------------------------------------------------------------
# This file lives at creative_pack/config.py
# Package root is one level up.
_PACKAGE_DIR = Path(__file__).parent
_PROJECT_ROOT = _PACKAGE_DIR.parent

BRAND_KITS_DIR = _PROJECT_ROOT / "brand_kits"
TEMPLATES_DIR = _PROJECT_ROOT / "templates"
OUTPUT_DIR = _PROJECT_ROOT / "output"

# Ensure output dir exists at import time
OUTPUT_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Environment variables (all optional — graceful degradation to mock mode)
# ---------------------------------------------------------------------------
FAL_API_KEY = os.environ.get("FAL_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
SCREENSHOTONE_API_KEY = os.environ.get("SCREENSHOTONE_API_KEY", "")

# ---------------------------------------------------------------------------
# Platform specs
# ---------------------------------------------------------------------------
PLATFORM_SPECS: dict[str, dict] = {
    # Video (Phase 3)
    "meta_feed":        {"w": 1080, "h": 1080, "ratio": "1:1",    "fmt": "mp4"},
    "meta_story":       {"w": 1080, "h": 1920, "ratio": "9:16",   "fmt": "mp4"},
    "meta_reel":        {"w": 1080, "h": 1920, "ratio": "9:16",   "fmt": "mp4"},
    "tiktok":           {"w": 1080, "h": 1920, "ratio": "9:16",   "fmt": "mp4"},
    "youtube_short":    {"w": 1080, "h": 1920, "ratio": "9:16",   "fmt": "mp4"},
    "linkedin_video":   {"w": 1920, "h": 1080, "ratio": "16:9",   "fmt": "mp4"},
    # Static (Phase 1)
    "meta_static":      {"w": 1080, "h": 1080, "ratio": "1:1",    "fmt": "png"},
    "meta_story_img":   {"w": 1080, "h": 1920, "ratio": "9:16",   "fmt": "png"},
    "google_display":   {"w": 1200, "h": 628,  "ratio": "1.91:1", "fmt": "png"},
    "linkedin_static":  {"w": 1200, "h": 627,  "ratio": "1.91:1", "fmt": "png"},
    # Web assets (Phase 2)
    "hero_desktop":     {"w": 1920, "h": 1080, "ratio": "16:9",   "fmt": "jpg"},
    "hero_mobile":      {"w": 390,  "h": 844,  "ratio": "9:21",   "fmt": "jpg"},
    "hero_og":          {"w": 1200, "h": 630,  "ratio": "1.91:1", "fmt": "jpg"},
}

# Platform copy character limits (enforced by expander)
PLATFORM_COPY_LIMITS: dict[str, dict[str, int | None]] = {
    "meta_static":      {"headline": 40,  "body": 125},
    "meta_story_img":   {"headline": 40,  "body": None},
    "google_display":   {"headline": 30,  "body": 90},
    "linkedin_static":  {"headline": 150, "body": 600},
    "meta_feed":        {"headline": 40,  "body": 125},
    "meta_story":       {"headline": 40,  "body": None},
    "tiktok":           {"headline": None, "body": None},
    "youtube_short":    {"headline": None, "body": None},
    "meta_reel":        {"headline": None, "body": None},
    "linkedin_video":   {"headline": 150, "body": 600},
    "hero_desktop":     {"headline": 80,  "body": 200},
    "hero_mobile":      {"headline": 60,  "body": 150},
    "hero_og":          {"headline": 60,  "body": 120},
}


def get_platform_spec(platform: str) -> dict:
    """
    Return the spec dict for a platform.
    Raises KeyError if the platform is not registered.
    """
    if platform not in PLATFORM_SPECS:
        raise KeyError(
            f"Unknown platform '{platform}'. "
            f"Available: {list(PLATFORM_SPECS.keys())}"
        )
    return PLATFORM_SPECS[platform]


def get_copy_limits(platform: str) -> dict[str, int | None]:
    """Return copy character limits for a platform (defaults to large limits if unknown)."""
    return PLATFORM_COPY_LIMITS.get(platform, {"headline": 150, "body": 600})
