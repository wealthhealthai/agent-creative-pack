# Creative Capability Pack

**Phase 1 — Static Ad Generation**

Generates production-quality digital ad creative from a one-line brief.
Designed for the AXIA Marketing Agent (Helio Genomics).

---

## Quick Start

### 1. Install dependencies

```bash
# Core deps (no API keys needed for mock mode)
pip3 install pillow playwright requests colorthief python-dotenv

# Install Playwright Chromium browser
python3 -m playwright install chromium

# Full install (when you have API keys)
pip3 install -r requirements.txt
```

### 2. Set environment variables (optional — all fall back to mock mode)

```bash
export FAL_API_KEY="your_fal_key"          # fal.ai — Flux + BiRefNet
export ANTHROPIC_API_KEY="your_key"         # Claude — brief expansion
export SCREENSHOTONE_API_KEY="your_key"     # screenshotone.com — URL scraper fallback
```

Without API keys: Playwright compositor runs locally, placeholder PNG images are generated, and mock copy is used. Full pipeline still runs end-to-end.

### 3. Run the CLI

```bash
# Single platform, mock mode
python3 creative_pack/cli.py \
  --client helio_livertrace \
  --brief "LiverTrace DTC, warm hopeful, adults 40+" \
  --platforms meta_static \
  --output /tmp/creative-out/

# Full 9-ad set (3 platforms × 3 copy variants)
python3 creative_pack/cli.py \
  --client helio_livertrace \
  --brief "LiverTrace DTC, warm hopeful, adults 40+" \
  --platforms meta_static meta_story_img google_display \
  --variants 3 \
  --output /tmp/creative-out/

# With URL scraping (Phase 0)
python3 creative_pack/cli.py \
  --client helio_livertrace \
  --brief "DTC ad for liver health" \
  --product-url https://livertrace.com \
  --platforms meta_static \
  --output /tmp/creative-out/
```

**Output JSON:**
```json
{
  "status": "ok",
  "files": {
    "meta_static_v1": "/tmp/creative-out/exports/v1/meta_static_abc123.png",
    "meta_static_v2": "/tmp/creative-out/exports/v2/meta_static_def456.png"
  },
  "cost": 0.0,
  "job_id": "a1b2c3d4",
  "timestamp": "2026-04-23T07:00:00+00:00",
  "copy_variants": [...]
}
```

### 4. Run tests

```bash
cd /path/to/agent-creative-pack
python3 -m pytest tests/ -v
```

---

## Pipeline Architecture

```
[BRIEF] → [0. SCRAPE] → [1. EXPAND] → [2. ASSETS] → [3. GENERATE] → [4. COMPOSITE] → [5. EXPORT]
           (optional)     Claude        BiRefNet        Flux 1.1 Pro    HTML/CSS→         PIL resize
           Playwright               (bg removal)       (images)         Playwright        per platform
```

| Stage | Module | Mock Behavior |
|-------|--------|---------------|
| 0 | `scraper.py` | Returns minimal ProductAsset |
| 1 | `expander.py` | Returns placeholder PAS/AIDA/emotional copy |
| 2 | `assets.py` | Downloads image as-is (no bg removal) |
| 3 | `generator.py` | Generates solid-color placeholder PNG |
| 4 | `compositor.py` | Renders HTML template via Playwright (full) |
| 5 | `exporter.py` | Resizes PNG to platform dimensions via PIL |

---

## Platform Specs

| Platform Key | Dimensions | Format |
|---|---|---|
| `meta_static` | 1080×1080 | PNG |
| `meta_story_img` | 1080×1920 | PNG |
| `google_display` | 1200×628 | PNG |
| `linkedin_static` | 1200×627 | PNG |
| `hero_desktop` | 1920×1080 | JPG |
| `hero_mobile` | 390×844 | JPG |
| `hero_og` | 1200×630 | JPG |
| `meta_feed` (video) | 1080×1080 | MP4 (Phase 3) |
| `meta_story` (video) | 1080×1920 | MP4 (Phase 3) |

---

## Adding a New Client Brand Kit

1. Create `brand_kits/your_client.json`:

```json
{
  "client_id": "your_client",
  "product_name": "Your Product",
  "logo_url": "https://yoursite.com/logo.png",
  "logo_position": "top-right",
  "primary_color": "#000000",
  "accent_color": "#FF6600",
  "background_color": "#FFFFFF",
  "font_headline": "Inter",
  "font_headline_weight": "700",
  "font_body": "Inter",
  "font_body_weight": "400",
  "cta_style": "rounded-pill",
  "cta_color": "#FF6600",
  "disclaimer_required": false,
  "disclaimer_text": "",
  "style_default": "clean",
  "image_style": "lifestyle-emotional",
  "fda_guardrails": false,
  "guardrail_terms_blocked": [],
  "guardrail_terms_required": [],
  "music_default": null
}
```

2. Run the CLI with `--client your_client`. Done.

---

## Adding a New Platform

Edit `creative_pack/config.py` and add an entry to `PLATFORM_SPECS`:

```python
PLATFORM_SPECS["pinterest_pin"] = {
    "w": 1000, "h": 1500, "ratio": "2:3", "fmt": "png"
}
```

And add copy limits to `PLATFORM_COPY_LIMITS`:

```python
PLATFORM_COPY_LIMITS["pinterest_pin"] = {"headline": 100, "body": 500}
```

The export stage will automatically handle the new platform.

---

## Templates

HTML/CSS ad templates in `templates/`:

| Template | Layout | Best For |
|---|---|---|
| `lifestyle.html` | Full-bleed bg image, copy bottom-left | DTC consumer (LiverTrace) |
| `product_hero.html` | Split: image left, copy right | Physician-facing (HelioLiver) |
| `minimal.html` | Centered, lots of whitespace | Brand awareness, retargeting |

Templates use CSS variables (`--primary-color`, `--accent-color`, etc.) and
data attributes (`data-headline`, `data-body`, etc.) that the compositor injects.
No Python changes needed to update visual design — just edit the HTML/CSS.

---

## Brand Kits

| Kit | Client | Use |
|---|---|---|
| `helio_livertrace.json` | Helio Genomics / LiverTrace | DTC consumer, warm/hopeful, FDA guardrails ON |
| `helio_helioliver.json` | Helio Genomics / HelioLiver | Physician-facing, clinical, stricter guardrails |

---

## Phase Roadmap

- **Phase 1** (current) — Static ads: Meta, Google Display, LinkedIn
- **Phase 2** — Website hero assets: URL scraping + vision model brief
- **Phase 3** — Video ads: Kling 3.0 + MoviePy + music bed
