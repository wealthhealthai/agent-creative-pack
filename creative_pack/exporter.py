"""
Stage 5 — Platform Export
==========================
Resizes/crops the composited master image to each platform's exact dimensions.
Uses PIL for final resize (NOT for compositing — just geometry).
"""

from __future__ import annotations

import sys

import os
import uuid
from pathlib import Path

from creative_pack.config import get_platform_spec, PLATFORM_SPECS


def _resize_image(
    source_path: str,
    output_path: str,
    width: int,
    height: int,
    fmt: str,
) -> str:
    """
    Resize and crop an image to the target dimensions using PIL.

    Strategy: scale to fill (cover), then center-crop.
    This preserves aspect ratio while filling the target canvas.
    """
    try:
        from PIL import Image

        img = Image.open(source_path).convert("RGB")
        src_w, src_h = img.size

        # Scale to fill — determine scale factor
        scale_w = width / src_w
        scale_h = height / src_h
        scale = max(scale_w, scale_h)

        new_w = int(src_w * scale)
        new_h = int(src_h * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)

        # Center crop
        left = (new_w - width) // 2
        top = (new_h - height) // 2
        img = img.crop((left, top, left + width, top + height))

        # Save
        pil_format = "JPEG" if fmt.lower() in ("jpg", "jpeg") else "PNG"
        save_kwargs: dict = {}
        if pil_format == "JPEG":
            save_kwargs["quality"] = 92
            save_kwargs["optimize"] = True
        img.save(output_path, pil_format, **save_kwargs)
        return output_path

    except Exception as e:
        print(f"[exporter] PIL resize failed: {e} — copying source", file=sys.stderr)
        import shutil
        shutil.copy2(source_path, output_path)
        return output_path


def export_to_platforms(
    source_image: str,
    platforms: list[str],
    output_dir: str,
) -> dict[str, str]:
    """
    Export a composited master image to all requested platform dimensions.

    Args:
        source_image:  Local path to the composited PNG from Stage 4.
        platforms:     List of platform keys (e.g. ["meta_static", "meta_story_img"]).
        output_dir:    Directory to write resized output files.

    Returns:
        Dict mapping platform → local file path.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    results: dict[str, str] = {}

    for platform in platforms:
        try:
            spec = get_platform_spec(platform)
        except KeyError:
            print(f"[exporter] Unknown platform '{platform}' — skipping", file=sys.stderr)
            continue

        width = spec["w"]
        height = spec["h"]
        fmt = spec["fmt"]

        # Skip video platforms (Phase 3)
        if fmt == "mp4":
            print(f"[exporter] Platform '{platform}' is video (Phase 3, file=sys.stderr) — skipping")
            continue

        ext = fmt.lower()
        fname = f"{platform}_{uuid.uuid4().hex[:6]}.{ext}"
        output_path = os.path.join(output_dir, fname)

        result = _resize_image(source_image, output_path, width, height, fmt)
        results[platform] = result

    return results


def calculate_cost(platforms: list[str], has_fal_key: bool) -> float:
    """
    Estimate API cost for generating a set of platform exports.

    Phase 1 static costs:
      - Flux 1.1 Pro: $0.04/image
      - BiRefNet: free
      - Playwright rendering: $0.00 (local)
      - Platform export: $0.00 (PIL)
    
    When mocked (no FAL key): $0.00
    When live: $0.04 per generated image (charged at generation stage)
    """
    if not has_fal_key:
        return 0.0

    # Static platforms only (video not included in Phase 1)
    static_count = sum(
        1
        for p in platforms
        if PLATFORM_SPECS.get(p, {}).get("fmt", "png") != "mp4"
    )

    # Flux charge is per generation run (not per export).
    # This function returns the export-stage cost only.
    # Generation cost is added by the caller in __init__.py.
    # Here we just note screenshotone might be used.
    return 0.0
