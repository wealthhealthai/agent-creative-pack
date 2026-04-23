"""
Stage 3 — AI Image Generation
================================
Generates lifestyle or product-hero background images using Flux 1.1 Pro via fal.ai.
Falls back to solid-color placeholder PNGs when FAL_API_KEY is not set.
"""

from __future__ import annotations

import sys

import os
import uuid
from pathlib import Path

import requests

from creative_pack.config import FAL_API_KEY, get_platform_spec
from creative_pack.models import BrandKit, CopySet, CreativeBrief


def _make_output_path(output_dir: str, platform: str) -> str:
    """Build a unique output file path for a generated image."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    fname = f"gen_{platform}_{uuid.uuid4().hex[:8]}.png"
    return os.path.join(output_dir, fname)


def _generate_placeholder(output_path: str, width: int, height: int, color: tuple) -> str:
    """Generate a solid-color placeholder PNG at exact platform dimensions."""
    try:
        from PIL import Image

        img = Image.new("RGB", (width, height), color)
        img.save(output_path, "PNG")
        return output_path
    except Exception as e:
        print(f"[generator] PIL placeholder failed: {e}")
        # Write a minimal 1x1 valid PNG as last resort
        _write_minimal_png(output_path)
        return output_path


def _write_minimal_png(path: str) -> None:
    """Write a minimal 1×1 white PNG — absolutely no dependencies."""
    import struct
    import zlib

    def chunk(name: bytes, data: bytes) -> bytes:
        c = name + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr = chunk(b"IHDR", ihdr_data)
    raw_data = b"\x00\xff\xff\xff"  # filter byte + RGB
    idat = chunk(b"IDAT", zlib.compress(raw_data))
    iend = chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(sig + ihdr + idat + iend)


def generate_image(
    prompt: str,
    platform: str,
    output_dir: str,
    style: str = "lifestyle",
) -> str:
    """
    Generate a background image for an ad.

    - If FAL_API_KEY set: calls fal-ai/flux-pro/v1.1 at platform dimensions.
    - Otherwise: generates a solid-color placeholder PNG.

    Returns the local file path of the generated image.
    """
    spec = get_platform_spec(platform) if platform in _KNOWN_PLATFORMS() else {
        "w": 1080, "h": 1080, "fmt": "png"
    }
    width, height = spec["w"], spec["h"]
    output_path = _make_output_path(output_dir, platform)

    if FAL_API_KEY:
        return _generate_via_fal(prompt, width, height, output_path)
    else:
        # Warm blue-grey placeholder
        placeholder_color = (26, 63, 111)  # Helio primary blue as default
        return _generate_placeholder(output_path, width, height, placeholder_color)


def _KNOWN_PLATFORMS() -> set[str]:
    from creative_pack.config import PLATFORM_SPECS
    return set(PLATFORM_SPECS.keys())


def _generate_via_fal(prompt: str, width: int, height: int, output_path: str) -> str:
    """Call fal-ai/flux-pro/v1.1 and download the result."""
    try:
        import fal_client

        result = fal_client.run(
            "fal-ai/flux-pro/v1.1",
            arguments={
                "prompt": prompt,
                "image_size": {"width": width, "height": height},
                "num_images": 1,
                "output_format": "png",
                "safety_tolerance": "2",
            },
        )

        images = result.get("images", [])
        if images:
            img_url = images[0].get("url", "")
            if img_url:
                headers = {"User-Agent": "CreativePack/1.0"}
                resp = requests.get(img_url, headers=headers, timeout=60, stream=True)
                resp.raise_for_status()
                with open(output_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                return output_path

        print("[generator] fal returned no image URL — using placeholder", file=sys.stderr)
        return _generate_placeholder(output_path, width, height, (26, 63, 111))

    except Exception as e:
        print(f"[generator] fal error: {e} — using placeholder", file=sys.stderr)
        return _generate_placeholder(output_path, width, height, (26, 63, 111))


def build_image_prompt(
    brief: CreativeBrief,
    brand_kit: BrandKit,
    copy_set: CopySet,
) -> str:
    """
    Construct a Flux 1.1 Pro image prompt from the creative brief.

    - Lifestyle/emotional style: person + emotion + context + product
    - Clinical/product-focused style (helio_helioliver): product-only, clean
    """
    product_name = brand_kit.product_name

    # Use image_direction from brief if it looks specific
    if brief.image_direction and len(brief.image_direction) > 30:
        base_prompt = brief.image_direction
    else:
        # Build from style
        if brand_kit.image_style == "product-focused":
            base_prompt = (
                f"{product_name} kit on clean white surface, clinical lighting, "
                f"professional product photography, crisp focus, neutral background, "
                f"pharmaceutical packaging aesthetic"
            )
        else:
            # Default: lifestyle-emotional (DTC health)
            # "person + emotion + context + product"
            style_modifiers = {
                "warm-clinical": "soft warm tones, morning light",
                "clinical": "clean neutral tones, diffuse lighting",
                "warm": "warm golden hour light, cozy setting",
                "clean": "bright airy light, minimal clean background",
                "energetic": "vibrant natural light, active setting",
            }
            lighting = style_modifiers.get(brief.style, "natural light")
            base_prompt = (
                f"35-year-old adult at home, looking at phone with visible relief and hope, "
                f"{product_name} kit open in front of them, {lighting}, "
                f"photorealistic lifestyle photography, Canon 5D bokeh, "
                f"warm and trustworthy aesthetic, depth of field"
            )

    # Append quality modifiers
    quality_suffix = (
        ", 4K photorealistic, professional photography, "
        "sharp focus, high-quality advertising photography"
    )

    return (base_prompt + quality_suffix).strip()
