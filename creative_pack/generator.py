"""
Stage 3 — AI image generation via fal.ai Flux 1.1 Pro.
Falls back to placeholder PNG if FAL_API_KEY not set.
"""
import os
import uuid
from pathlib import Path
from .models import CreativeBrief, CopySet, BrandKit
from .config import FAL_API_KEY, MOCK_MODE, get_platform_spec, get_model_config, DEFAULT_MODEL


def build_image_prompt(brief: CreativeBrief, brand_kit: BrandKit, copy_set: CopySet) -> str:
    """
    Build a Flux-optimized image generation prompt.
    Strategy: person + emotion + context + product (lifestyle-first).
    Exception: physician-facing (product-focused) gets product-only prompt.
    """
    style = brief.style
    product = brand_kit.product_name

    if brand_kit.image_style == "product-focused":
        # Physician-facing: clean product shot
        return (
            f"{product} medical test kit on clean white surface, "
            f"clinical lighting, sharp focus, professional product photography, "
            f"minimalist healthcare aesthetic, high resolution"
        )

    # DTC / consumer: lifestyle-emotional
    # Use the image_direction from the expanded brief if available
    if brief.image_direction:
        return brief.image_direction

    # Fallback construction
    demographic = "adult in their 40s"
    emotion = "looking at phone with visible relief and hope"
    context = "at home, kitchen table, morning light"
    lighting = "soft warm natural light, golden hour"
    camera = "Canon 5D, shallow depth of field, bokeh background"

    if style == "warm":
        lighting = "soft warm natural light, golden hour tones"
    elif style == "clinical":
        lighting = "bright clinical white light, clean and sterile"
    elif style == "energetic":
        lighting = "bright dynamic light, high contrast"

    return (
        f"{demographic}, {emotion}, {context}, {product} kit visible, "
        f"{lighting}, {camera}, photorealistic, 8K resolution"
    )


def _generate_placeholder(platform: str, output_dir: str, index: int = 0) -> str:
    """Generate a solid-color placeholder PNG at platform dimensions."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        # Absolute fallback: write a minimal 1x1 PNG
        output_path = Path(output_dir) / f"placeholder_{platform}_{index}.png"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Minimal valid PNG bytes (1x1 white pixel)
        import struct, zlib
        def make_png(w, h, color=(30, 80, 140)):
            raw = b'\x00' + bytes(color) + b'\xff'  # filter byte + RGB + alpha
            raw = raw * w
            raw = b'\x00' + raw[1:]  # fix filter
            # Just write a simple solid color PNG
            pass
        output_path.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)
        return str(output_path)

    spec = get_platform_spec(platform)
    w, h = spec["w"], spec["h"]

    # Brand-ish colors for placeholder
    colors = [
        (26, 63, 111),   # #1A3F6F — Helio primary blue
        (0, 180, 216),   # #00B4D8 — Helio accent
        (42, 42, 80),    # dark
        (20, 100, 140),  # mid blue
    ]
    color = colors[index % len(colors)]

    img = Image.new("RGB", (w, h), color=color)
    draw = ImageDraw.Draw(img)

    # Draw placeholder text
    text_lines = [
        f"[MOCK IMAGE]",
        f"Platform: {platform}",
        f"{w} × {h}",
        "Replace with Flux generation",
    ]
    y = h // 2 - 60
    for line in text_lines:
        try:
            bbox = draw.textbbox((0, 0), line)
            tw = bbox[2] - bbox[0]
        except Exception:
            tw = len(line) * 7
        x = (w - tw) // 2
        draw.text((x, y), line, fill=(255, 255, 255))
        y += 30

    fmt = spec.get("fmt", "png")
    ext = "jpg" if fmt == "jpg" else "png"
    output_path = Path(output_dir) / f"generated_{platform}_{index}.{ext}"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if ext == "jpg":
        img = img.convert("RGB")
        img.save(str(output_path), "JPEG", quality=90)
    else:
        img.save(str(output_path), "PNG")

    print(f"[generator] Mock image saved: {output_path}")
    return str(output_path)


def generate_image(
    prompt: str,
    platform: str,
    output_dir: str,
    style: str = "lifestyle",
    index: int = 0,
    model: str | None = None,
) -> str:
    """
    Generate a background image for an ad.
    model: one of the keys in IMAGE_MODELS (e.g. 'flux-pro', 'recraft-v3', 'nano-banana-pro')
    Falls back to placeholder PNG in mock mode.
    Returns local file path.
    """
    model = model or DEFAULT_MODEL
    if MOCK_MODE or not FAL_API_KEY:
        print(f"[generator] MOCK MODE — would call {model} with: {prompt[:80]}...")
        return _generate_placeholder(platform, output_dir, index)

    try:
        model_cfg = get_model_config(model)
    except ValueError as e:
        print(f"[generator] {e}, falling back to placeholder")
        return _generate_placeholder(platform, output_dir, index)

    spec = get_platform_spec(platform)
    w, h = spec["w"], spec["h"]
    output_path = Path(output_dir) / f"generated_{platform}_{model}_{index}.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    provider = model_cfg["provider"]

    # ── Google (Nano Banana Pro) ──────────────────────────────────────────
    if provider == "google":
        return _generate_google(prompt, model_cfg["id"], output_path, w, h)

    # ── fal.ai ────────────────────────────────────────────────────────────
    return _generate_fal(prompt, model_cfg["id"], output_path, w, h, platform, index)


def _generate_fal(prompt: str, model_id: str, output_path: Path, w: int, h: int,
                  platform: str, index: int) -> str:
    try:
        import fal_client, requests
        kwargs = {
            "prompt": prompt,
            "image_size": {"width": w, "height": h},
            "num_images": 1,
            "output_format": "png",
        }
        # Recraft uses slightly different schema
        if "recraft" in model_id:
            kwargs["style"] = "realistic_image"
            del kwargs["output_format"]
        else:
            kwargs["num_inference_steps"] = 28
            kwargs["guidance_scale"] = 3.5

        result = fal_client.run(model_id, arguments=kwargs)
        image_url = result["images"][0]["url"]
        r = requests.get(image_url, timeout=60)
        r.raise_for_status()
        output_path.write_bytes(r.content)
        print(f"[generator] {model_id} → {output_path}")
        return str(output_path)
    except Exception as e:
        print(f"[generator] fal.ai ({model_id}) failed: {e}, falling back to placeholder")
        from .config import get_platform_spec
        return _generate_placeholder(platform if platform else "meta_static",
                                     str(output_path.parent), index)


def _generate_google(prompt: str, model_id: str, output_path: Path, w: int, h: int) -> str:
    """Generate via Nano Banana Pro (Google Gemini Image API)."""
    import os, subprocess, sys
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if not gemini_key:
        from .config import PACKAGE_ROOT
        import json
        try:
            oc_config = PACKAGE_ROOT.parent.parent.parent / ".openclaw" / "openclaw.json"
            with open(oc_config) as f:
                d = json.load(f)
            gemini_key = d.get("skills", {}).get("entries", {}).get("nano-banana-pro", {}).get("apiKey", "")
        except Exception:
            pass

    if not gemini_key:
        print("[generator] No GEMINI_API_KEY — falling back to placeholder")
        return _generate_placeholder("meta_static", str(output_path.parent), 0)

    skill_script = "/opt/homebrew/lib/node_modules/openclaw/skills/nano-banana-pro/scripts/generate_image.py"
    result = subprocess.run(
        ["uv", "run", skill_script,
         "--prompt", prompt,
         "--filename", str(output_path),
         "--resolution", "1K"],
        capture_output=True, text=True, timeout=120,
        env={**os.environ, "GEMINI_API_KEY": gemini_key}
    )
    if result.returncode == 0 and output_path.exists():
        print(f"[generator] Nano Banana Pro → {output_path}")
        return str(output_path)
    else:
        print(f"[generator] Nano Banana Pro failed: {result.stderr[:200]}")
        return _generate_placeholder("meta_static", str(output_path.parent), 0)
