"""
Stage 0 — URL Scraper
=====================
Extracts product metadata, images, and brand colors from a product URL.

Priority order:
  1. Playwright stealth (handles most sites)
  2. screenshotone.com + Claude vision (fallback for bot-protected sites)
  3. Minimal ProductAsset with URL only (last resort)
"""

from __future__ import annotations

import sys

import os
import re
import tempfile
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

from creative_pack.models import ProductAsset


def _extract_colors_from_image(image_path: str, count: int = 5) -> list[str]:
    """Use colorthief to extract dominant hex colors from an image file."""
    try:
        from colorthief import ColorThief

        ct = ColorThief(image_path)
        palette = ct.get_palette(color_count=count, quality=3)
        return [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in palette]
    except Exception:
        return []


def _download_image(url: str, dest_path: str) -> bool:
    """Download an image URL to dest_path. Returns True on success."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; CreativePack/1.0)"}
        resp = requests.get(url, headers=headers, timeout=20, stream=True)
        resp.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception:
        return False


def _scrape_with_playwright(url: str) -> Optional[ProductAsset]:
    """
    Use Playwright (with stealth headers) to scrape a product page.
    Returns ProductAsset or None if it fails.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None

    tmp = tempfile.mkdtemp(prefix="creative_pack_scrape_")
    screenshot_path = os.path.join(tmp, "screenshot.png")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1440, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": (
                        "text/html,application/xhtml+xml,application/xml;q=0.9,"
                        "image/avif,image/webp,*/*;q=0.8"
                    ),
                },
            )
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)

            # Extract Open Graph metadata
            og_title = page.evaluate(
                "() => { const m = document.querySelector('meta[property=\"og:title\"]'); "
                "return m ? m.content : document.title || ''; }"
            )
            og_description = page.evaluate(
                "() => { const m = document.querySelector('meta[property=\"og:description\"]'); "
                "if (m) return m.content; "
                "const d = document.querySelector('meta[name=\"description\"]'); "
                "return d ? d.content : ''; }"
            )
            og_image = page.evaluate(
                "() => { const m = document.querySelector('meta[property=\"og:image\"]'); "
                "return m ? m.content : ''; }"
            )

            # Collect large images
            all_images: list[str] = page.evaluate(
                """() => {
                    const imgs = Array.from(document.querySelectorAll('img'));
                    return imgs
                        .filter(img => img.naturalWidth > 400 || img.width > 400)
                        .map(img => img.src)
                        .filter(src => src && src.startsWith('http'))
                        .slice(0, 10);
                }"""
            )

            # Existing copy (taglines, h1)
            existing_copy = page.evaluate(
                "() => { const h = document.querySelector('h1'); return h ? h.innerText : ''; }"
            ) or og_title or ""

            # Price extraction
            price = page.evaluate(
                """() => {
                    const priceSelectors = [
                        '[data-price]', '.price', '#price', '.product-price',
                        '[itemprop="price"]', '.a-price-whole'
                    ];
                    for (const sel of priceSelectors) {
                        const el = document.querySelector(sel);
                        if (el) return el.innerText.trim().slice(0, 20);
                    }
                    return null;
                }"""
            )

            # Full-page screenshot
            page.screenshot(path=screenshot_path, full_page=True)
            context.close()
            browser.close()

        # Extract brand colors from og:image or screenshot
        brand_colors: list[str] = []
        hero_for_colors = og_image or (all_images[0] if all_images else None)
        if hero_for_colors:
            img_tmp = os.path.join(tmp, "hero_color.png")
            if _download_image(hero_for_colors, img_tmp):
                brand_colors = _extract_colors_from_image(img_tmp)
        if not brand_colors and os.path.exists(screenshot_path):
            brand_colors = _extract_colors_from_image(screenshot_path)

        hero_images = [img for img in [og_image] + all_images if img]

        return ProductAsset(
            product_name=og_title or urlparse(url).netloc,
            description=og_description or "",
            price=price,
            hero_images=hero_images[:6],
            brand_colors=brand_colors,
            existing_copy=existing_copy,
            page_screenshot_url=screenshot_path,
        )

    except Exception as e:
        print(f"[scraper] Playwright failed: {e}", file=sys.stderr)
        return None


def _scrape_with_screenshotone(url: str) -> Optional[ProductAsset]:
    """
    Fallback: use screenshotone.com API to capture screenshot,
    then use Claude vision to extract product details.
    """
    from creative_pack.config import SCREENSHOTONE_API_KEY, ANTHROPIC_API_KEY

    if not SCREENSHOTONE_API_KEY:
        return None

    screenshot_url = (
        f"https://api.screenshotone.com/take"
        f"?url={url}"
        f"&access_key={SCREENSHOTONE_API_KEY}"
        f"&full_page=true"
        f"&viewport_width=1440"
        f"&viewport_height=900"
        f"&format=png"
    )

    if ANTHROPIC_API_KEY:
        # Use Claude vision to extract product details
        try:
            from anthropic import Anthropic

            client = Anthropic()
            response = client.messages.create(
                model="claude-opus-4-5",
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "url",
                                    "url": screenshot_url,
                                },
                            },
                            {
                                "type": "text",
                                "text": (
                                    "Extract from this webpage screenshot: "
                                    "1) Product name, 2) Short description (1-2 sentences), "
                                    "3) Price if visible, 4) Main headline/tagline. "
                                    "Reply in JSON: {\"product_name\": ..., \"description\": ..., "
                                    "\"price\": ..., \"existing_copy\": ...}"
                                ),
                            },
                        ],
                    }
                ],
            )
            import json

            raw = response.content[0].text
            # Extract JSON from response
            json_match = re.search(r"\{.*\}", raw, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return ProductAsset(
                    product_name=data.get("product_name", urlparse(url).netloc),
                    description=data.get("description", ""),
                    price=data.get("price"),
                    hero_images=[screenshot_url],
                    brand_colors=[],
                    existing_copy=data.get("existing_copy", ""),
                    page_screenshot_url=screenshot_url,
                )
        except Exception as e:
            print(f"[scraper] screenshotone+Claude vision failed: {e}")

    # Return minimal asset with screenshot URL only
    return ProductAsset(
        product_name=urlparse(url).netloc,
        description="",
        price=None,
        hero_images=[screenshot_url],
        brand_colors=[],
        existing_copy="",
        page_screenshot_url=screenshot_url,
    )


def scrape_url(url: str) -> ProductAsset:
    """
    Stage 0: Scrape a product or website URL and return a ProductAsset.

    Tries:
      1. Playwright stealth
      2. screenshotone.com + Claude vision (if SCREENSHOTONE_API_KEY set)
      3. Minimal ProductAsset with URL as fallback
    """
    # Always try screenshotone first if key is set (more reliable)
    from creative_pack.config import SCREENSHOTONE_API_KEY

    result: Optional[ProductAsset] = None

    if SCREENSHOTONE_API_KEY:
        result = _scrape_with_screenshotone(url)
    else:
        result = _scrape_with_playwright(url)
        if result is None:
            result = _scrape_with_screenshotone(url)

    if result is not None:
        return result

    # Last resort: minimal asset
    print(f"[scraper] All methods failed for {url} — returning minimal ProductAsset", file=sys.stderr)
    return ProductAsset(
        product_name=urlparse(url).netloc,
        description="",
        price=None,
        hero_images=[],
        brand_colors=[],
        existing_copy="",
        page_screenshot_url="",
    )
