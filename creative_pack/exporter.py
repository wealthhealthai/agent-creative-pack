"""
Stage 5 — Platform export: resize/crop to platform specs and save in correct format.
PIL is appropriate here — this is just resize, not creative compositing.
"""
from pathlib import Path
from .config import get_platform_spec, PLATFORM_SPECS


def export_to_platforms(
    source_image: str,
    platforms: list[str],
    output_dir: str,
    suffix: str = "",
) -> dict[str, str]:
    """
    Resize and export a source image to all requested platform dimensions.
    Returns dict of platform → output file path.
    """
    try:
        from PIL import Image
    except ImportError:
        raise RuntimeError("Pillow not installed. Run: pip install Pillow")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results = {}

    src = Image.open(source_image)
    if src.mode not in ("RGB", "RGBA"):
        src = src.convert("RGB")

    for platform in platforms:
        spec = get_platform_spec(platform)
        w, h = spec["w"], spec["h"]
        fmt = spec.get("fmt", "png")

        if fmt == "mp4":
            # Skip video platforms in static export
            print(f"[exporter] Skipping video platform: {platform}")
            continue

        # Smart crop/resize: scale to fill, then center crop
        img = src.copy()
        src_ratio = img.width / img.height
        tgt_ratio = w / h

        if src_ratio > tgt_ratio:
            # Source is wider — scale by height
            new_h = h
            new_w = int(img.width * h / img.height)
        else:
            # Source is taller — scale by width
            new_w = w
            new_h = int(img.height * w / img.width)

        img = img.resize((new_w, new_h), Image.LANCZOS)

        # Center crop
        left = (new_w - w) // 2
        top = (new_h - h) // 2
        img = img.crop((left, top, left + w, top + h))

        # Save
        sfx = f"_{suffix}" if suffix else ""
        ext = "jpg" if fmt == "jpg" else "png"
        filename = f"{platform}{sfx}_export.{ext}"
        out_path = output_dir / filename

        if ext == "jpg":
            img.convert("RGB").save(str(out_path), "JPEG", quality=92)
        else:
            img.save(str(out_path), "PNG")

        results[platform] = str(out_path)
        print(f"[exporter] {platform} → {out_path} ({w}×{h})")

    return results


def calculate_cost(platforms: list[str], has_fal_key: bool) -> float:
    """Estimate API cost for a run."""
    if not has_fal_key:
        return 0.0
    static_platforms = [p for p in platforms if PLATFORM_SPECS.get(p, {}).get("fmt") != "mp4"]
    # Flux: ~$0.04/image, BiRefNet: ~$0.01
    return round(len(static_platforms) * 0.04 + 0.01, 4)
