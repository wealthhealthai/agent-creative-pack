"""
Stage 4 — HTML/CSS → Playwright Compositor
===========================================
Renders ad templates at exact platform viewport dimensions using Playwright.
This is the production-quality compositor — NOT PIL.

Templates live in templates/*.html and use:
  - CSS variables for brand colors/fonts
  - data attributes on .ad-container for dynamic copy
  - JavaScript inside the template to populate DOM from data attributes
"""

from __future__ import annotations

import sys

import base64
import os
import uuid
from pathlib import Path

from creative_pack.config import get_platform_spec, TEMPLATES_DIR
from creative_pack.models import BrandKit, CopySet


def _image_to_base64_data_url(image_path: str) -> str:
    """
    Convert a local image file to a base64 data URL for embedding in HTML.
    Falls back to a solid-color CSS gradient if the image cannot be read.
    """
    if not image_path or not os.path.exists(image_path):
        # Return a CSS gradient fallback (will be used as background-image)
        return ""

    try:
        with open(image_path, "rb") as f:
            raw = f.read()
        # Detect image type from magic bytes
        if raw[:8] == b"\x89PNG\r\n\x1a\n":
            mime = "image/png"
        elif raw[:2] == b"\xff\xd8":
            mime = "image/jpeg"
        elif raw[:4] == b"GIF8":
            mime = "image/gif"
        elif raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
            mime = "image/webp"
        else:
            mime = "image/png"
        b64 = base64.b64encode(raw).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except Exception as e:
        print(f"[compositor] Could not read image {image_path}: {e}", file=sys.stderr)
        return ""


def _load_template(template_name: str) -> str:
    """Load an HTML template from the templates/ directory."""
    # template_name can be "lifestyle", "product_hero", or "minimal"
    if not template_name.endswith(".html"):
        template_name += ".html"

    template_path = TEMPLATES_DIR / template_name
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


def _inject_content(
    html: str,
    image_data_url: str,
    copy_set: CopySet,
    brand_kit: BrandKit,
) -> str:
    """
    Inject brand values and copy data into the HTML template.

    Replaces CSS variable declarations and sets data attributes
    on the .ad-container element.

    The template's JavaScript reads these and populates the DOM.
    """
    # Escape values for safe HTML attribute insertion
    def esc(s: str) -> str:
        if not s:
            return ""
        return (
            s.replace("&", "&amp;")
            .replace('"', "&quot;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    headline = esc(copy_set.headline or "")
    body = esc(copy_set.body or "")
    cta = esc(copy_set.cta or "Learn More")
    disclaimer = esc(copy_set.disclaimer or "")
    logo_url = esc(brand_kit.logo_url or "")

    # CSS variable block — injected into :root
    bg_css = f"url('{image_data_url}')" if image_data_url else (
        f"linear-gradient(135deg, {brand_kit.primary_color} 0%, {brand_kit.accent_color} 100%)"
    )

    css_vars = f"""
    :root {{
        --primary-color: {brand_kit.primary_color};
        --accent-color: {brand_kit.accent_color};
        --cta-color: {brand_kit.cta_color};
        --background-color: {brand_kit.background_color};
        --font-headline: '{brand_kit.font_headline}', sans-serif;
        --font-body: '{brand_kit.font_body}', sans-serif;
        --font-headline-weight: {brand_kit.font_headline_weight};
        --font-body-weight: {brand_kit.font_body_weight};
        --bg-image: {bg_css};
        --logo-url: url('{logo_url}');
    }}
    """.strip()

    # Inject CSS vars into <style> block — replace the sentinel comment
    if "/* :root-vars */" in html:
        html = html.replace("/* :root-vars */", css_vars)
    elif ":root {" in html:
        # Replace existing :root block
        import re
        html = re.sub(r":root\s*\{[^}]*\}", css_vars, html, count=1)
    else:
        # Inject before </style>
        html = html.replace("</style>", css_vars + "\n</style>", 1)

    # Set data attributes on .ad-container
    data_attrs = (
        f' data-headline="{headline}"'
        f' data-body="{body}"'
        f' data-cta="{cta}"'
        f' data-disclaimer="{disclaimer}"'
    )

    # Replace the placeholder data attributes marker or inject into existing tag
    if 'class="ad-container"' in html:
        html = html.replace(
            'class="ad-container"',
            f'class="ad-container"{data_attrs}',
            1,
        )
    elif "class='ad-container'" in html:
        html = html.replace(
            "class='ad-container'",
            f"class='ad-container'{data_attrs}",
            1,
        )

    return html


def composite_ad(
    image_path: str,
    copy_set: CopySet,
    brand_kit: BrandKit,
    platform: str,
    template: str,
    output_dir: str,
) -> str:
    """
    Stage 4 main function — renders an HTML/CSS ad template via Playwright.

    Args:
        image_path:  Local path to the background image (from Stage 3).
        copy_set:    Copy variant to render.
        brand_kit:   Client brand configuration.
        platform:    Target platform (controls viewport dimensions).
        template:    Template name: "lifestyle", "product_hero", or "minimal".
        output_dir:  Directory to write the output PNG.

    Returns:
        Local file path of the rendered PNG.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Get platform viewport
    try:
        spec = get_platform_spec(platform)
    except KeyError:
        spec = {"w": 1080, "h": 1080, "fmt": "png"}
    width, height = spec["w"], spec["h"]

    # Build output path
    fname = f"composite_{platform}_{copy_set.framework}_{uuid.uuid4().hex[:6]}.png"
    output_path = os.path.join(output_dir, fname)

    # Convert background image to base64 data URL (avoids file:// CORS issues in Playwright)
    image_data_url = _image_to_base64_data_url(image_path)

    # Load and prepare template
    html_content = _load_template(template)
    html_content = _inject_content(html_content, image_data_url, copy_set, brand_kit)

    # Write temp HTML file
    tmp_html = os.path.join(output_dir, f"_tmp_{uuid.uuid4().hex[:8]}.html")
    with open(tmp_html, "w", encoding="utf-8") as f:
        f.write(html_content)

    try:
        _render_with_playwright(tmp_html, output_path, width, height)
    finally:
        # Clean up temp HTML
        if os.path.exists(tmp_html):
            os.remove(tmp_html)

    return output_path


def _render_with_playwright(
    html_path: str,
    output_path: str,
    width: int,
    height: int,
) -> None:
    """
    Use Playwright sync API to render an HTML file and take a screenshot.

    Viewport is set to exact platform dimensions.
    """
    from playwright.sync_api import sync_playwright

    file_url = f"file://{os.path.abspath(html_path)}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": width, "height": height},
            device_scale_factor=1,
        )
        page = context.new_page()
        page.goto(file_url, wait_until="networkidle", timeout=30_000)

        # Wait for any JS animations / font loads to settle
        page.wait_for_timeout(500)

        # Screenshot at exact viewport (no scrolling)
        page.screenshot(
            path=output_path,
            full_page=False,
            clip={"x": 0, "y": 0, "width": width, "height": height},
        )
        context.close()
        browser.close()
