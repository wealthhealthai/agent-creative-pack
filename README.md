# Forge Imagine

**Internal codename:** Forge Imagine
**Package:** `agent-creative-pack`

Reusable Python capability pack that turns any AI agent into a marketing creative expert. Generates production-quality digital ad creative from a plain-language brief.

Built by WealthHealth AI — Forge Enterprise Division.

---

## Pipeline

```
[BRIEF/URL] → [0. SCRAPE] → [1. EXPAND] → [2. ASSETS] → [3. GENERATE] → [4. COMPOSITE] → [5. EXPORT]
```

- **Stage 0** — Optional: scrape product URL for context
- **Stage 1** — LLM expands brief into 3 copy variants (PAS / AIDA / emotional)
- **Stage 2** — BiRefNet removes product image background
- **Stage 3** — Flux 1.1 Pro generates lifestyle/hero background image
- **Stage 4** — HTML/CSS templates → Playwright screenshot at exact platform dims
- **Stage 5** — Resize/export to all requested platform formats

Runs fully in **mock mode** (no API keys) for development and testing.

---

## Installation

```bash
pip install -r requirements.txt
playwright install chromium
```

## Environment Variables

```bash
# Required for live generation (optional for mock mode)
export ANTHROPIC_API_KEY=sk-ant-...   # Brief expansion via Claude
export FAL_API_KEY=...                # Flux image generation + BiRefNet
export SCREENSHOTONE_API_KEY=...      # URL scraper fallback
```

---

## CLI Usage

```bash
# Full ad set — 3 platforms, 3 copy variants
python3 creative_pack/cli.py \
  --client helio_livertrace \
  --brief "LiverTrace DTC, warm hopeful, adults 40+" \
  --platforms meta_static meta_story_img google_display \
  --output /tmp/helio-ads/

# Single static ad
python3 creative_pack/cli.py \
  --client helio_livertrace \
  --brief "Know your liver risk" \
  --platforms meta_static \
  --variants 1

# With product image URL
python3 creative_pack/cli.py \
  --client helio_livertrace \
  --brief "Home liver test kit" \
  --platforms meta_static \
  --product-image https://livertrace.com/images/kit.jpg

# Physician-facing (product_hero template)
python3 creative_pack/cli.py \
  --client helio_helioliver \
  --brief "HelioLiver LDT oncologist targeting" \
  --platforms google_display linkedin_static \
  --template product_hero
```

Output is JSON to stdout:
```json
{
  "status": "ok",
  "job_id": "a3f2b1c4",
  "files": {
    "meta_static_v1_PAS": "/tmp/helio-ads/meta_static_pas_0.png",
    "meta_static_v2_AIDA": "/tmp/helio-ads/meta_static_aida_1.png"
  },
  "copy_variants": [...],
  "cost": 0.12
}
```

---

## Python API

```python
from creative_pack import generate_ad_set, generate_static, generate_variants

# Full ad set
result = generate_ad_set(
    brief="LiverTrace DTC, warm hopeful",
    client_id="helio_livertrace",
    platforms=["meta_static", "meta_story_img", "google_display"],
)
print(result.files)  # {platform_variant: file_path}

# Single quick static
path = generate_static("test ad", "helio_livertrace", "meta_static")

# A/B variants
paths = generate_variants("test ad", "helio_livertrace", "meta_static", count=3)
```

---

## Adding a New Client

1. Create `brand_kits/<client_id>.json` (copy helio_livertrace.json as template)
2. Create 3 HTML templates in `templates/` or reuse existing ones
3. Done — full pipeline works immediately

## Adding a New Platform

Add one entry to `PLATFORM_SPECS` in `creative_pack/config.py`:
```python
"snapchat_story": {"w": 1080, "h": 1920, "ratio": "9:16", "fmt": "png"},
```

---

## Image Generation Model Guide

Choose based on desired aesthetic. All available on fal.ai (or Google API for Nano Banana Pro).

| Model | fal.ai ID | Cost | Best For | Notes |
|-------|-----------|------|----------|-------|
| **Nano Banana Pro** | Google API (`gemini-3-pro-image-preview`) | ~$0.04 | **Maximum photorealism** — our top pick for DTC health ads | Gemini 3 Pro Image. Wins on convincing real-world skin/lighting. |
| **Recraft V3** | `fal-ai/recraft-v3` | ~$0.04 | **Cinematic / lifestyle feel** — dramatic, editorial look | Excellent style consistency. Great for emotional/aspirational DTC. |
| **Flux 1.1 Pro Ultra** | `fal-ai/flux-pro/v1.1-ultra` | ~$0.06 | High quality general purpose | Upgrade from Flux 1.1 Pro. Good all-rounder. |
| **Flux 1.1 Pro** | `fal-ai/flux-pro/v1.1` | $0.04 | Default / budget baseline | Default in pipeline. Solid quality. |
| **Flux Kontext Pro** | `fal-ai/flux-kontext/pro` | ~$0.08 | **Product compositing + iterative editing** | NOT text-to-image. Takes an existing scene + places real product photo in naturally. Use for product-in-scene compositing (Phase 2). |

**Recommended defaults by use case:**
- DTC health (consumer-facing): **Nano Banana Pro** (realism) or **Recraft V3** (cinematic)
- Physician-facing / clinical: **Recraft V3** (clean, professional)
- Product compositing: **Flux Kontext Pro** as post-generation step
- Budget / high volume: **Flux 1.1 Pro**

Set via `generator.py` model string or `--model` CLI flag (coming in next update).

## Supported Platforms

| Platform | Dimensions | Format |
|----------|-----------|--------|
| meta_static | 1080×1080 | PNG |
| meta_story_img | 1080×1920 | PNG |
| google_display | 1200×628 | PNG |
| linkedin_static | 1200×627 | PNG |
| hero_desktop | 1920×1080 | JPG |
| hero_mobile | 390×844 | JPG |

---

## Running Tests

```bash
pytest tests/ -v
```

Tests run fully in mock mode — no API keys required.

---

## Phase Roadmap

- **Phase 1** ✅ Static image ads (current)
- **Phase 2** — Website hero assets (URL → vision → Flux → hero image)
- **Phase 3** — Video ads (Kling 3.0 + MoviePy)
- **Phase 4** — UGC/voiceover (ElevenLabs + lipsync)
