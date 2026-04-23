"""
Stage 2 — Asset preparation: background removal via BiRefNet, upscaling.
Falls back to simple download if FAL_API_KEY not set.
"""
import os
import requests
from pathlib import Path
from .config import FAL_API_KEY, MOCK_MODE


def remove_background(image_url: str, output_path: str) -> str:
    """
    Remove background from a product image using BiRefNet v2 via fal.ai.
    Falls back to simple download (no bg removal) if FAL_API_KEY not set.
    Returns local file path.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if MOCK_MODE or not FAL_API_KEY:
        print(f"[assets] MOCK MODE — downloading image without bg removal: {image_url[:60]}")
        try:
            r = requests.get(image_url, timeout=30)
            r.raise_for_status()
            output_path.write_bytes(r.content)
        except Exception as e:
            print(f"[assets] Download failed ({e}), creating placeholder")
            _write_placeholder(output_path)
        return str(output_path)

    # TODO: Real BiRefNet call
    try:
        import fal_client
        result = fal_client.run(
            "fal-ai/birefnet-v2",
            arguments={"image_url": image_url}
        )
        result_url = result["image"]["url"]
        r = requests.get(result_url, timeout=60)
        r.raise_for_status()
        output_path.write_bytes(r.content)
        print(f"[assets] Background removed: {output_path}")
        return str(output_path)
    except Exception as e:
        print(f"[assets] BiRefNet failed ({e}), falling back to direct download")
        try:
            r = requests.get(image_url, timeout=30)
            r.raise_for_status()
            output_path.write_bytes(r.content)
        except Exception:
            _write_placeholder(output_path)
        return str(output_path)


def _write_placeholder(path: Path) -> None:
    """Write a transparent placeholder PNG."""
    try:
        from PIL import Image
        img = Image.new("RGBA", (800, 800), (200, 200, 200, 128))
        img.save(str(path), "PNG")
    except ImportError:
        path.write_bytes(b"")


def upscale_image(image_path: str) -> str:
    """Upscale image via ESRGAN if needed. Currently stubbed — returns input."""
    # TODO: fal-ai/esrgan integration
    print(f"[assets] Upscale stub — returning original: {image_path}")
    return image_path


def prepare_product_asset(image_url: str, output_dir: str) -> str:
    """
    Full asset prep pipeline: download → remove background → return clean PNG path.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "product_nobg.png"
    return remove_background(image_url, str(output_path))
