"""
Stage 4 — HTML/CSS → Playwright compositor.
Renders ad templates at exact platform viewport dimensions.
This is the quality core of the pipeline — no PIL for text/layout.
"""
import base64
import json
import os
import re
import tempfile
import uuid
from pathlib import Path
from string import Template

from .models import CopySet, BrandKit
from .config import TEMPLATES_DIR, get_platform_spec, get_copy_limits

# Template name → file
TEMPLATE_FILES = {
    "lifestyle":     "lifestyle.html",
    "product_hero":  "product_hero.html",
    "minimal":       "minimal.html",
}


def _truncate_copy_for_platform(copy_set: CopySet, platform: str) -> CopySet:
    """Return a copy of CopySet with text truncated to this platform's character limits."""
    import copy as copy_module
    cs = copy_module.copy(copy_set)
    lim = get_copy_limits(platform)
    hl_max = lim.get("headline", 0)
    body_max = lim.get("body", 0)
    if hl_max and len(cs.headline) > hl_max:
        cs.headline = cs.headline[:hl_max - 1] + "…"
    if body_max == 0:
        cs.body = ""
    elif body_max and len(cs.body) > body_max:
        cs.body = cs.body[:body_max - 1] + "…"
    return cs


def _image_to_data_url(image_path: str) -> str:
    """Convert a local image file to a base64 data URL for embedding in HTML."""
    path = Path(image_path)
    if not path.exists():
        return ""
    ext = path.suffix.lower().lstrip(".")
    mime = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "webp": "image/webp",
    }.get(ext, "image/png")
    data = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{data}"


def _load_template(template_name: str) -> str:
    """Load an HTML template file."""
    filename = TEMPLATE_FILES.get(template_name, f"{template_name}.html")
    template_path = TEMPLATES_DIR / filename
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")
    return template_path.read_text()


def _inject_content(html: str, copy_set: CopySet, brand_kit: BrandKit, bg_data_url: str) -> str:
    """
    Inject dynamic content into the HTML template by replacing
    CSS variables and data attributes.
    """
    # Build the CSS variables block
    css_vars = f"""
        --primary-color: {brand_kit.primary_color};
        --accent-color: {brand_kit.accent_color};
        --background-color: {brand_kit.background_color};
        --cta-color: {brand_kit.cta_color};
        --font-headline: '{brand_kit.font_headline}', sans-serif;
        --font-body: '{brand_kit.font_body}', sans-serif;
        --font-headline-weight: {brand_kit.font_headline_weight};
        --font-body-weight: {brand_kit.font_body_weight};
        --bg-image: url('{bg_data_url}');
        --logo-url: url('{brand_kit.logo_url}');
    """

    # Escape content for HTML attribute injection
    def esc(s: str) -> str:
        if not s:
            return ""
        return s.replace('"', '&quot;').replace("'", "&#39;")

    # Replace CSS vars placeholder
    html = html.replace("/* __CSS_VARS__ */", css_vars)

    # Replace data attributes on the ad container
    html = html.replace('data-headline=""', f'data-headline="{esc(copy_set.headline)}"')
    html = html.replace('data-body=""', f'data-body="{esc(copy_set.body)}"')
    html = html.replace('data-cta=""', f'data-cta="{esc(copy_set.cta)}"')
    disclaimer = copy_set.disclaimer or ""
    html = html.replace('data-disclaimer=""', f'data-disclaimer="{esc(disclaimer)}"')
    html = html.replace('data-show-disclaimer="false"',
                        f'data-show-disclaimer="{"true" if disclaimer else "false"}"')
    html = html.replace('data-logo-url=""', f'data-logo-url="{esc(brand_kit.logo_url)}"')

    # Inject Google Fonts
    google_font = brand_kit.font_headline
    font_link = f'<link href="https://fonts.googleapis.com/css2?family={google_font.replace(" ", "+")}:wght@400;700;900&display=swap" rel="stylesheet">'
    html = html.replace("<!-- __GOOGLE_FONTS__ -->", font_link)

    return html


def composite_ad(
    image_path: str,
    copy_set: CopySet,
    brand_kit: BrandKit,
    platform: str,
    template: str,
    output_dir: str,
    variant_index: int = 0,
) -> str:
    """
    Render an ad by injecting content into an HTML template and
    screenshotting via Playwright at the exact platform viewport.

    Returns the path to the output PNG file.
    """
    spec = get_platform_spec(platform)
    w, h = spec["w"], spec["h"]
    fmt = spec.get("fmt", "png")

    # Truncate copy to this platform's character limits
    copy_set = _truncate_copy_for_platform(copy_set, platform)

    # Convert background image to data URL for embedding
    bg_data_url = _image_to_data_url(image_path) if image_path else ""

    # Load and populate template
    html = _load_template(template)
    html = _inject_content(html, copy_set, brand_kit, bg_data_url)

    # Write populated HTML to temp file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", delete=False, encoding="utf-8"
    ) as f:
        f.write(html)
        tmp_html = f.name

    # Screenshot via Playwright
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    safe_framework = re.sub(r"[^a-z0-9]", "_", copy_set.framework.lower())
    filename = f"{platform}_{safe_framework}_{variant_index}.png"
    out_file = output_path / filename

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError(
            "Playwright not installed. Run: pip install playwright && playwright install chromium"
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": w, "height": h})
        page.goto(f"file://{tmp_html}")
        # Wait for fonts and images to load
        page.wait_for_load_state("networkidle", timeout=10000)
        page.screenshot(path=str(out_file), full_page=False, clip={"x": 0, "y": 0, "width": w, "height": h})
        browser.close()

    os.unlink(tmp_html)

    # If platform wants jpg, convert
    if fmt == "jpg" and out_file.suffix == ".png":
        jpg_file = out_file.with_suffix(".jpg")
        try:
            from PIL import Image
            img = Image.open(out_file).convert("RGB")
            img.save(str(jpg_file), "JPEG", quality=92)
            out_file.unlink()
            out_file = jpg_file
        except ImportError:
            pass  # keep as PNG

    print(f"[compositor] Rendered: {out_file} ({w}×{h})")
    return str(out_file)


def composite_all_variants(
    image_path: str,
    copy_variants: list[CopySet],
    brand_kit: BrandKit,
    platform: str,
    template: str,
    output_dir: str,
) -> list[str]:
    """Composite all copy variants for a single platform. Returns list of file paths."""
    results = []
    for i, copy_set in enumerate(copy_variants):
        path = composite_ad(
            image_path=image_path,
            copy_set=copy_set,
            brand_kit=brand_kit,
            platform=platform,
            template=template,
            output_dir=output_dir,
            variant_index=i,
        )
        results.append(path)
    return results
