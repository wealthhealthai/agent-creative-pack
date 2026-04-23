"""
Stage 0 (optional) — URL scraper.
Extracts product name, description, images, brand colors from a URL.
Uses Playwright stealth; falls back to screenshotone.com API.
"""
import json
import re
import tempfile
import os
from pathlib import Path
from .models import ProductAsset
from .config import SCREENSHOTONE_API_KEY


def scrape_url(url: str) -> ProductAsset:
    """
    Scrape a product or website URL to extract structured ProductAsset.
    Tries Playwright stealth first; falls back to screenshotone + Claude vision.
    """
    print(f"[scraper] Scraping: {url}")
    try:
        return _scrape_with_playwright(url)
    except Exception as e:
        print(f"[scraper] Playwright failed ({e}), trying screenshotone fallback...")
        try:
            return _scrape_with_screenshotone(url)
        except Exception as e2:
            print(f"[scraper] Screenshotone fallback failed ({e2}), returning minimal asset")
            return ProductAsset(
                product_name=_extract_domain(url),
                description="",
                hero_images=[],
                brand_colors=[],
                existing_copy="",
                page_screenshot_url="",
            )


def _extract_domain(url: str) -> str:
    m = re.search(r"(?:https?://)?(?:www\.)?([^/]+)", url)
    return m.group(1) if m else url


def _scrape_with_playwright(url: str) -> ProductAsset:
    """Playwright stealth scraper."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError("Playwright not installed")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(2000)

        # Take screenshot
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            screenshot_path = f.name
        page.screenshot(path=screenshot_path, full_page=True)

        # Extract metadata
        data = page.evaluate("""() => {
            const getMeta = (name) => {
                const el = document.querySelector(`meta[property="${name}"], meta[name="${name}"]`);
                return el ? el.getAttribute('content') : null;
            };
            const imgs = Array.from(document.querySelectorAll('img'))
                .filter(img => img.naturalWidth > 300 && img.src)
                .map(img => img.src)
                .slice(0, 5);
            return {
                title: getMeta('og:title') || document.title || '',
                description: getMeta('og:description') || getMeta('description') || '',
                image: getMeta('og:image') || '',
                images: imgs,
            };
        }""")

        browser.close()

        # Extract brand colors from screenshot
        colors = []
        try:
            from colorthief import ColorThief
            ct = ColorThief(screenshot_path)
            palette = ct.get_palette(color_count=5, quality=5)
            colors = [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in palette]
        except Exception:
            pass
        finally:
            try:
                os.unlink(screenshot_path)
            except Exception:
                pass

        hero_images = []
        if data.get("image"):
            hero_images.append(data["image"])
        hero_images.extend(data.get("images", []))
        hero_images = list(dict.fromkeys(hero_images))[:5]  # dedupe, max 5

        return ProductAsset(
            product_name=data.get("title", "").strip(),
            description=data.get("description", "").strip(),
            hero_images=hero_images,
            brand_colors=colors,
            existing_copy=data.get("title", ""),
            page_screenshot_url="",
        )


def _scrape_with_screenshotone(url: str) -> ProductAsset:
    """Screenshotone.com fallback — takes a screenshot and uses Claude vision to parse."""
    if not SCREENSHOTONE_API_KEY:
        raise RuntimeError("SCREENSHOTONE_API_KEY not set")

    screenshot_url = (
        f"https://api.screenshotone.com/take"
        f"?url={url}"
        f"&access_key={SCREENSHOTONE_API_KEY}"
        f"&full_page=true"
        f"&format=png"
    )

    # Use Claude vision to extract product details from screenshot
    from .config import ANTHROPIC_API_KEY
    if not ANTHROPIC_API_KEY:
        return ProductAsset(
            product_name=_extract_domain(url),
            description="",
            hero_images=[screenshot_url],
            brand_colors=[],
            existing_copy="",
            page_screenshot_url=screenshot_url,
        )

    try:
        from anthropic import Anthropic
        import requests

        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        r = requests.get(screenshot_url, timeout=30)
        r.raise_for_status()
        import base64
        img_b64 = base64.b64encode(r.content).decode()

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/png", "data": img_b64}
                    },
                    {
                        "type": "text",
                        "text": (
                            "Extract from this webpage screenshot: "
                            "product name, one-sentence description, main product image URL if visible, "
                            "primary brand colors (hex codes). "
                            "Return JSON: {product_name, description, hero_image_url, brand_colors: [hex,...]}"
                        )
                    }
                ]
            }]
        )

        raw = response.content[0].text.strip()
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw)

        return ProductAsset(
            product_name=data.get("product_name", ""),
            description=data.get("description", ""),
            hero_images=[data["hero_image_url"]] if data.get("hero_image_url") else [],
            brand_colors=data.get("brand_colors", []),
            existing_copy=data.get("product_name", ""),
            page_screenshot_url=screenshot_url,
        )
    except Exception as e:
        print(f"[scraper] Vision extraction failed ({e})")
        return ProductAsset(
            product_name=_extract_domain(url),
            description="",
            hero_images=[],
            brand_colors=[],
            existing_copy="",
            page_screenshot_url=screenshot_url,
        )
