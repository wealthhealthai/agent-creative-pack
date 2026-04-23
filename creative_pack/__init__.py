"""
Creative Capability Pack — Phase 1 (Static Ads)
Reusable Python module for AI-powered ad creative generation.
"""
import json
import uuid
from datetime import datetime
from pathlib import Path

from .models import BrandKit, AdJobResult, WebAssetResult
from .config import load_brand_kit, OUTPUT_DIR, MOCK_MODE
from .expander import expand_brief
from .generator import generate_image, build_image_prompt
from .compositor import composite_ad
from .exporter import export_to_platforms, calculate_cost


def get_brand_kit(client_id: str) -> BrandKit:
    """Load and return a BrandKit by client ID."""
    data = load_brand_kit(client_id)
    return BrandKit.from_dict(data)


def generate_ad_set(
    brief: str,
    client_id: str,
    platforms: list[str],
    product_image_url: str | None = None,
    product_url: str | None = None,
    copy_variants: int = 3,
    output_mode: str = "ad",
    template: str = "lifestyle",
    output_dir: str | None = None,
) -> AdJobResult:
    """
    Full pipeline: brief → expanded copy → image → composite → export.
    Returns AdJobResult with per-platform file paths, copy variants, and cost.
    """
    job_id = str(uuid.uuid4())[:8]
    output_dir = output_dir or str(OUTPUT_DIR / job_id)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    brand_kit = get_brand_kit(client_id)

    # Stage 0 — URL scraping (optional)
    product_asset = None
    if product_url:
        try:
            from .scraper import scrape_url
            product_asset = scrape_url(product_url)
        except Exception as e:
            print(f"[pipeline] Scraping failed ({e}), continuing without product asset")

    # Stage 1 — Brief expansion
    creative_brief = expand_brief(
        brief=brief,
        brand_kit=brand_kit,
        platforms=platforms,
        product_asset=product_asset,
    )
    creative_brief.platforms = platforms
    creative_brief.output_mode = output_mode

    # Select copy variants (up to requested count)
    selected_variants = creative_brief.copy_variants[:copy_variants]

    # Stage 2 — Asset prep (if product image provided)
    if product_image_url:
        from .assets import prepare_product_asset
        product_image_url = prepare_product_asset(product_image_url, output_dir)

    # Stage 3 + 4 — Generate background image and composite for each platform
    all_files = {}

    for platform in platforms:
        # Generate one background image per platform
        prompt = build_image_prompt(creative_brief, brand_kit, selected_variants[0])
        bg_image = generate_image(
            prompt=prompt,
            platform=platform,
            output_dir=output_dir,
            style=creative_brief.style,
        )

        # Composite each copy variant
        for i, copy_set in enumerate(selected_variants):
            out_path = composite_ad(
                image_path=bg_image,
                copy_set=copy_set,
                brand_kit=brand_kit,
                platform=platform,
                template=template,
                output_dir=output_dir,
                variant_index=i,
            )
            key = f"{platform}_v{i+1}_{copy_set.framework}"
            all_files[key] = out_path

    cost = calculate_cost(platforms, not MOCK_MODE)

    return AdJobResult(
        files=all_files,
        copy_variants=selected_variants,
        cost=cost,
        job_id=job_id,
        timestamp=datetime.utcnow().isoformat(),
    )


def generate_static(brief: str, client_id: str, platform: str, output_dir: str | None = None) -> str:
    """Quick single static ad — returns file path of first variant."""
    result = generate_ad_set(
        brief=brief,
        client_id=client_id,
        platforms=[platform],
        copy_variants=1,
        output_dir=output_dir,
    )
    files = list(result.files.values())
    return files[0] if files else ""


def generate_variants(
    brief: str, client_id: str, platform: str, count: int = 3, output_dir: str | None = None
) -> list[str]:
    """Generate multiple creative variants for A/B testing. Returns list of file paths."""
    result = generate_ad_set(
        brief=brief,
        client_id=client_id,
        platforms=[platform],
        copy_variants=min(count, 3),
        output_dir=output_dir,
    )
    return list(result.files.values())
