"""
Configuration, platform specs, paths, and environment loading.
"""
import os
import json
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
PACKAGE_ROOT = Path(__file__).parent.parent
BRAND_KITS_DIR = PACKAGE_ROOT / "brand_kits"
TEMPLATES_DIR = PACKAGE_ROOT / "templates"
OUTPUT_DIR = PACKAGE_ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── Environment ────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(PACKAGE_ROOT / ".env")
except ImportError:
    pass

FAL_API_KEY = os.environ.get("FAL_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
SCREENSHOTONE_API_KEY = os.environ.get("SCREENSHOTONE_API_KEY", "")

MOCK_MODE = not bool(FAL_API_KEY)  # True = use placeholders instead of real API calls

# ── Platform Specs ─────────────────────────────────────────────────────────
PLATFORM_SPECS = {
    # Static
    "meta_static":      {"w": 1080, "h": 1080, "ratio": "1:1",     "fmt": "png"},
    "meta_story_img":   {"w": 1080, "h": 1920, "ratio": "9:16",    "fmt": "png"},
    "google_display":   {"w": 1200, "h": 628,  "ratio": "1.91:1",  "fmt": "png"},
    "linkedin_static":  {"w": 1200, "h": 627,  "ratio": "1.91:1",  "fmt": "png"},
    # Video
    "meta_feed":        {"w": 1080, "h": 1080, "ratio": "1:1",     "fmt": "mp4"},
    "meta_story":       {"w": 1080, "h": 1920, "ratio": "9:16",    "fmt": "mp4"},
    "meta_reel":        {"w": 1080, "h": 1920, "ratio": "9:16",    "fmt": "mp4"},
    "tiktok":           {"w": 1080, "h": 1920, "ratio": "9:16",    "fmt": "mp4"},
    "youtube_short":    {"w": 1080, "h": 1920, "ratio": "9:16",    "fmt": "mp4"},
    "linkedin_video":   {"w": 1920, "h": 1080, "ratio": "16:9",    "fmt": "mp4"},
    # Web
    "hero_desktop":     {"w": 1920, "h": 1080, "ratio": "16:9",    "fmt": "jpg"},
    "hero_mobile":      {"w": 390,  "h": 844,  "ratio": "9:21",    "fmt": "jpg"},
    "hero_og":          {"w": 1200, "h": 630,  "ratio": "1.91:1",  "fmt": "jpg"},
}

# ── Copy character limits per platform ────────────────────────────────────
PLATFORM_COPY_LIMITS = {
    "meta_static":      {"headline": 40,  "body": 125},
    "meta_story_img":   {"headline": 40,  "body": 0},
    "google_display":   {"headline": 30,  "body": 90},
    "linkedin_static":  {"headline": 150, "body": 600},
    "meta_feed":        {"headline": 40,  "body": 125},
    "tiktok":           {"headline": 0,   "body": 0},
    "default":          {"headline": 80,  "body": 200},
}


def get_platform_spec(platform: str) -> dict:
    if platform not in PLATFORM_SPECS:
        raise ValueError(f"Unknown platform: {platform}. Available: {list(PLATFORM_SPECS.keys())}")
    return PLATFORM_SPECS[platform]


# ── Image generation model registry ───────────────────────────────────────
IMAGE_MODELS = {
    # Text-to-image (no image input)
    "flux-pro":           {"id": "fal-ai/flux-pro/v1.1",            "provider": "fal",    "cost": 0.04, "img2img": False, "note": "Default baseline"},
    "flux-ultra":         {"id": "fal-ai/flux-pro/v1.1-ultra",       "provider": "fal",    "cost": 0.06, "img2img": False, "note": "High quality general purpose"},
    "recraft-v3":         {"id": "fal-ai/recraft-v3",                "provider": "fal",    "cost": 0.04, "img2img": False, "note": "Cinematic/lifestyle feel — text only"},
    # Multimodal (understands + reconstructs product faithfully)
    "nano-banana-pro":    {"id": "gemini-3-pro-image-preview",       "provider": "google", "cost": 0.04, "img2img": True,  "note": "Maximum photorealism + MULTIMODAL — faithfully reconstructs products from photo"},
    # Image-to-image / reference variants (style reference, NOT faithful reconstruction)
    "flux-ultra-redux":   {"id": "fal-ai/flux-pro/v1.1-ultra/redux", "provider": "fal",    "cost": 0.06, "img2img": True,  "note": "Flux Ultra img2img — style variation from reference"},
    "recraft-v3-i2i":     {"id": "fal-ai/recraft/v3/image-to-image", "provider": "fal",    "cost": 0.04, "img2img": True,  "note": "Recraft img2img — style reference"},
    # Editing / compositing (Phase 2)
    "kontext-pro":        {"id": "fal-ai/flux-kontext/pro",          "provider": "fal",    "cost": 0.08, "img2img": True,  "note": "Surgical product compositing + scene editing — Phase 2"},
    "flux2-edit":         {"id": "fal-ai/flux-2-pro/edit",           "provider": "fal",    "cost": 0.08, "img2img": True,  "note": "Multi-reference editing up to 9 images — Phase 2"},
}
DEFAULT_MODEL = "flux-pro"


def get_model_config(model_name: str) -> dict:
    if model_name not in IMAGE_MODELS:
        raise ValueError(f"Unknown model: {model_name}. Available: {list(IMAGE_MODELS.keys())}")
    return IMAGE_MODELS[model_name]


def get_copy_limits(platform: str) -> dict:
    return PLATFORM_COPY_LIMITS.get(platform, PLATFORM_COPY_LIMITS["default"])


def load_brand_kit(client_id: str) -> dict:
    """Load brand kit JSON for a client."""
    path = BRAND_KITS_DIR / f"{client_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Brand kit not found: {path}")
    with open(path) as f:
        return json.load(f)
