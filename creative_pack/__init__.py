"""
Creative Capability Pack — Phase 1 (Static Ads)
================================================
Exposes the primary tool interfaces for the AXIA Marketing Agent.
"""

from __future__ import annotations

import sys

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from creative_pack.models import (
    AdJobResult,
    BrandKit,
    CopySet,
    CreativeBrief,
    ProductAsset,
    WebAssetResult,
)
from creative_pack.config import get_platform_spec, OUTPUT_DIR


def get_brand_kit(client_id: str) -> BrandKit:
    """Load a BrandKit from the brand_kits/ directory."""
    from creative_pack.config import BRAND_KITS_DIR

    kit_path = BRAND_KITS_DIR / f"{client_id}.json"
    if not kit_path.exists():
        raise FileNotFoundError(f"Brand kit not found: {kit_path}")
    with open(kit_path) as f:
        data = json.load(f)
    return BrandKit(**data)


def generate_static(brief: str, client_id: str, platform: str) -> str:
    """Quick single-static shortcut — returns output file path."""
    result = generate_ad_set(
        brief=brief,
        client_id=client_id,
        platforms=[platform],
        copy_variants=1,
    )
    files = result.files
    return list(files.values())[0] if files else ""


def generate_variants(
    brief: str, client_id: str, platform: str, count: int = 3
) -> list[str]:
    """Generate A/B/C creative variants for a single platform."""
    result = generate_ad_set(
        brief=brief,
        client_id=client_id,
        platforms=[platform],
        copy_variants=count,
    )
    return list(result.files.values())


def generate_ad_set(
    brief: str,
    client_id: str,
    platforms: list[str],
    product_image_url: str | None = None,
    product_url: str | None = None,
    copy_variants: int = 3,
    output_mode: str = "ad",
    output_dir: str | None = None,
) -> AdJobResult:
    """
    Full ad set pipeline: brief → scrape → expand → assets → generate → composite → export.

    Returns AdJobResult with file paths, copy variants, cost, and job metadata.
    """
    from creative_pack.scraper import scrape_url
    from creative_pack.expander import expand_brief
    from creative_pack.generator import generate_image, build_image_prompt
    from creative_pack.compositor import composite_ad
    from creative_pack.exporter import export_to_platforms, calculate_cost
    from creative_pack.config import FAL_API_KEY, TEMPLATES_DIR

    job_id = str(uuid.uuid4())[:8]
    ts = datetime.now(timezone.utc).isoformat()

    # Resolve output directory
    out_root = Path(output_dir) if output_dir else OUTPUT_DIR / job_id
    out_root.mkdir(parents=True, exist_ok=True)

    brand_kit = get_brand_kit(client_id)

    # Stage 0 — Optional URL scrape
    product_asset: ProductAsset | None = None
    if product_url:
        try:
            product_asset = scrape_url(product_url)
        except Exception as e:
            print(f"[scraper] warning: {e}")

    # Stage 1 — Brief expansion
    creative_brief = expand_brief(
        brief=brief,
        brand_kit=brand_kit,
        platforms=platforms,
        product_asset=product_asset,
    )

    has_fal = bool(FAL_API_KEY)

    # Choose template based on client style
    if brand_kit.image_style == "product-focused":
        template = "product_hero"
    else:
        template = "lifestyle"

    all_files: dict[str, str] = {}
    total_cost = 0.0

    # Use up to copy_variants variants
    variants_to_use = creative_brief.copy_variants[:copy_variants]

    # Stage 2+3 — Per-variant image generation
    gen_dir = out_root / "generated"
    gen_dir.mkdir(exist_ok=True)

    variant_images: list[str] = []
    for idx, copy_set in enumerate(variants_to_use):
        prompt = build_image_prompt(creative_brief, brand_kit, copy_set)
        # Use first platform's dimensions for generation
        primary_platform = platforms[0] if platforms else "meta_static"
        img_path = generate_image(
            prompt=prompt,
            platform=primary_platform,
            output_dir=str(gen_dir),
            style=creative_brief.style,
        )
        variant_images.append(img_path)
        if has_fal:
            total_cost += 0.04  # Flux cost per image

    # Stage 4 — Composite
    comp_dir = out_root / "composited"
    comp_dir.mkdir(exist_ok=True)

    composited: list[str] = []
    for idx, (copy_set, img_path) in enumerate(zip(variants_to_use, variant_images)):
        comp_path = composite_ad(
            image_path=img_path,
            copy_set=copy_set,
            brand_kit=brand_kit,
            platform=platforms[0] if platforms else "meta_static",
            template=template,
            output_dir=str(comp_dir),
        )
        composited.append(comp_path)

    # Stage 5 — Export to all platforms
    export_dir = out_root / "exports"
    export_dir.mkdir(exist_ok=True)

    for idx, comp_path in enumerate(composited):
        variant_label = f"v{idx+1}"
        platform_files = export_to_platforms(
            source_image=comp_path,
            platforms=platforms,
            output_dir=str(export_dir / variant_label),
        )
        for platform, fpath in platform_files.items():
            all_files[f"{platform}_{variant_label}"] = fpath

    total_cost += calculate_cost(platforms, has_fal)

    return AdJobResult(
        files=all_files,
        copy_variants=variants_to_use,
        cost=round(total_cost, 4),
        job_id=job_id,
        timestamp=ts,
    )


__all__ = [
    "generate_ad_set",
    "generate_static",
    "generate_variants",
    "get_brand_kit",
]
