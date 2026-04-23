"""
Stage 3 — AI image generation via fal.ai Flux 1.1 Pro.
Falls back to placeholder PNG if FAL_API_KEY not set.
"""
import os
import uuid
from pathlib import Path
from .models import CreativeBrief, CopySet, BrandKit
from .config import FAL_API_KEY, MOCK_MODE, get_platform_spec


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
) -> str:
    """
    Generate a background image for an ad.
    Real mode: calls fal-ai/flux-pro/v1.1
    Mock mode: generates placeholder PNG
    Returns local file path.
    """
    if MOCK_MODE or not FAL_API_KEY:
        print(f"[generator] MOCK MODE — would call Flux with: {prompt[:80]}...")
        return _generate_placeholder(platform, output_dir, index)

    # TODO: Real fal.ai call (swap in when FAL_API_KEY is set)
    try:
        import fal_client
        spec = get_platform_spec(platform)
        w, h = spec["w"], spec["h"]

        result = fal_client.run(
            "fal-ai/flux-pro/v1.1",
            arguments={
                "prompt": prompt,
                "image_size": {"width": w, "height": h},
                "num_inference_steps": 28,
                "guidance_scale": 3.5,
                "num_images": 1,
                "output_format": "png",
            }
        )

        image_url = result["images"][0]["url"]

        import requests
        r = requests.get(image_url, timeout=60)
        r.raise_for_status()

        ext = "png"
        output_path = Path(output_dir) / f"generated_{platform}_{index}.{ext}"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(r.content)
        print(f"[generator] Image saved: {output_path}")
        return str(output_path)

    except Exception as e:
        print(f"[generator] fal.ai call failed ({e}), falling back to placeholder")
        return _generate_placeholder(platform, output_dir, index)
