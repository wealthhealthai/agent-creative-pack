"""
Stage 2 — Asset Preparation
============================
Background removal (BiRefNet via fal.ai) and image upscaling.
Falls back to a simple download-and-save when FAL_API_KEY is not set.
"""

from __future__ import annotations

import sys

import os
import uuid
from pathlib import Path

import requests

from creative_pack.config import FAL_API_KEY


def remove_background(image_url: str, output_path: str) -> str:
    """
    Remove the background from a product image.

    - If FAL_API_KEY is set: calls fal-ai/birefnet-v2 and downloads result.
    - Otherwise: downloads the image as-is and saves it to output_path.

    Returns the local file path of the processed image.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    if FAL_API_KEY:
        return _remove_background_fal(image_url, output_path)
    else:
        return _remove_background_mock(image_url, output_path)


def _remove_background_fal(image_url: str, output_path: str) -> str:
    """Use fal-ai/birefnet-v2 to remove background."""
    try:
        import fal_client

        result = fal_client.run(
            "fal-ai/birefnet-v2",
            arguments={"image_url": image_url},
        )
        result_url = result.get("image", {}).get("url") or result.get("url", "")
        if result_url:
            _download_to(result_url, output_path)
            return output_path
        else:
            print("[assets] fal birefnet returned no URL — falling back to mock", file=sys.stderr)
            return _remove_background_mock(image_url, output_path)
    except Exception as e:
        print(f"[assets] fal birefnet error: {e} — falling back to mock", file=sys.stderr)
        return _remove_background_mock(image_url, output_path)


def _remove_background_mock(image_url: str, output_path: str) -> str:
    """
    Mock background removal: download image and save as PNG.
    No actual background removal — for use when FAL_API_KEY is not set.
    """
    if image_url.startswith("http"):
        downloaded = _download_to(image_url, output_path)
        if downloaded:
            # Convert to PNG using PIL if available
            try:
                from PIL import Image

                img = Image.open(output_path).convert("RGBA")
                # Save as PNG (preserve transparency if any)
                png_path = str(Path(output_path).with_suffix(".png"))
                img.save(png_path, "PNG")
                return png_path
            except Exception:
                return output_path
        return output_path
    elif os.path.exists(image_url):
        # Local file — just copy
        import shutil

        shutil.copy2(image_url, output_path)
        return output_path
    else:
        # Generate a placeholder PNG
        return _generate_placeholder_png(output_path)


def _download_to(url: str, dest_path: str) -> bool:
    """Download a URL to a local file path. Returns True on success."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; CreativePack/1.0)"}
        resp = requests.get(url, headers=headers, timeout=30, stream=True)
        resp.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"[assets] Download failed for {url}: {e}", file=sys.stderr)
        return False


def _generate_placeholder_png(output_path: str, width: int = 400, height: int = 400) -> str:
    """Generate a solid-color placeholder PNG."""
    try:
        from PIL import Image

        img = Image.new("RGBA", (width, height), (100, 180, 216, 255))
        png_path = str(Path(output_path).with_suffix(".png"))
        img.save(png_path, "PNG")
        return png_path
    except Exception as e:
        print(f"[assets] Could not generate placeholder: {e}", file=sys.stderr)
        return output_path


def upscale_image(image_path: str) -> str:
    """
    Upscale an image to higher resolution.
    Stub — returns input path. Phase 2 will add ESRGAN via fal.ai.
    """
    return image_path


def prepare_product_asset(image_url: str, output_dir: str) -> str:
    """
    Orchestrate background removal for a product image.

    Returns the local file path of the processed (bg-removed) image.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    fname = f"product_{uuid.uuid4().hex[:8]}.png"
    output_path = os.path.join(output_dir, fname)

    result_path = remove_background(image_url, output_path)
    return result_path
