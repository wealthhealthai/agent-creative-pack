# Creative Capability Pack — Vulcan Build Brief
**From:** Jason Li / Archon
**To:** Vulcan
**Date:** April 22, 2026
**Priority:** Medium — parallel to SOW execution, not blocking

---

## What This Is

A new build task. You are responsible for building, testing, and deploying the **Creative Capability Pack** — a Python module that gives the AXIA Marketing Agent (Helio) the ability to generate production-quality digital ad creative from a plain-language brief or product URL.

This is a Forge Enterprise capability. All enterprise agent builds are yours. Full spec is below and at:
`/Users/wealthhealth_admin/.openclaw/workspace-archon/projects/creative-pack/CREATIVE-CAPABILITY-PACK-SCOPE.md`

---

## Context

- **Client:** Helio Genomics (existing Forge Enterprise client)
- **Target agent:** AXIA Marketing Agent — one of the four Project AXIA agents in the pending Helio SOW
- **Why now:** AXIA SOW is being finalized. The creative pack is the Marketing Agent's primary capability. Build in parallel with SOW execution so it's ready at deployment.
- **First use case:** Generate LiverTrace DTC static image ads with headline, CTA, brand overlay, FDA disclaimer — from a one-line brief or a product URL.

---

## Helio's Three Use Cases (Priority Order)

1. **Static image ads** — LiverTrace DTC ads (Meta Feed, Meta Story, Google Display). Copy generated using DTC frameworks (PAS/AIDA), FDA guardrails applied automatically, Helio brand kit composited in. → Phase 1
2. **Website hero assets** — Scrape livertrace.com, auto-generate improvement brief via vision model, generate new hero imagery. → Phase 2
3. **Video ads** — 5-second product videos with music bed, for TikTok/Meta/YouTube Shorts. → Phase 3

---

## Tech Stack

| Layer | Tool | Notes |
|---|---|---|
| Image generation | fal.ai — Flux 1.1 Pro | $0.04/image, pay-per-use |
| Background removal | fal.ai — BiRefNet v2 | Free tier, commercial use OK |
| Video generation | fal.ai — Kling 3.0 Pro | $0.029/sec, ~$0.15 per 5-sec clip |
| URL scraping | Playwright (stealth) + screenshotone.com fallback | screenshotone ~$20/mo |
| Static compositor | HTML/CSS templates → Playwright screenshot | NOT PIL — see below |
| Video compositor | MoviePy + ffmpeg | Logo, text layers, music bed |
| Copy generation | Claude (via OpenClaw LLM) | PAS/AIDA/emotional frameworks |
| Language | Python 3.11+ | Runs on Helena VPS |

**Critical note on the compositor:** Do NOT use PIL/Pillow for the final ad output. PIL produces amateur typography. The correct approach is HTML/CSS templates rendered via Playwright at the exact platform viewport dimensions. Templates live as `.html` files with CSS variables for brand colors/fonts and data attributes for dynamic content (headline, image URL, CTA, disclaimer). This is how production ad tech works.

---

## Pipeline (Six Stages)

```
[BRIEF/URL] → [0. SCRAPE] → [1. EXPAND] → [2. ASSETS] → [3. GENERATE] → [4. COMPOSITE] → [5. EXPORT]
               (optional)                                      │                  │
                                                         Flux/Kling        HTML/CSS→Playwright
                                                                             (static)
                                                                             MoviePy (video)
```

0. **URL Scraper** — Playwright stealth extracts product images, name, description, brand colors. Screenshotone fallback for bot-protected sites.
1. **Brief Expansion** — LLM converts brief into structured `CreativeBrief`: headline, body, CTA, style, motion, 3 copy variants (PAS/AIDA/emotional). FDA guardrails injected for Helio.
2. **Asset Prep** — BiRefNet removes product background. Upscale via ESRGAN if needed.
3. **Generation** — Flux 1.1 Pro for lifestyle/hero scenes. Kling 3.0 for video. Image direction: person + emotion + context + product (not product-only).
4. **Compositing** — HTML/CSS templates → Playwright screenshot (static). MoviePy (video: logo bug, text animation, music bed).
5. **Export** — Renders to all requested platform specs from master.

---

## Platform Specs Dictionary

```python
PLATFORM_SPECS = {
    "meta_feed":       {"w": 1080, "h": 1080, "ratio": "1:1",    "fmt": "png"},
    "meta_story":      {"w": 1080, "h": 1920, "ratio": "9:16",   "fmt": "png"},
    "google_display":  {"w": 1200, "h": 628,  "ratio": "1.91:1", "fmt": "png"},
    "linkedin_static": {"w": 1200, "h": 627,  "ratio": "1.91:1", "fmt": "png"},
    "meta_reel":       {"w": 1080, "h": 1920, "ratio": "9:16",   "fmt": "mp4"},
    "tiktok":          {"w": 1080, "h": 1920, "ratio": "9:16",   "fmt": "mp4"},
    "youtube_short":   {"w": 1080, "h": 1920, "ratio": "9:16",   "fmt": "mp4"},
    "hero_desktop":    {"w": 1920, "h": 1080, "ratio": "16:9",   "fmt": "jpg"},
    "hero_mobile":     {"w": 390,  "h": 844,  "ratio": "9:21",   "fmt": "jpg"},
}
```

---

## Helio Brand Kits (Two Configs)

**`helio_livertrace`** — consumer/DTC
- Tone: warm, hopeful, accessible
- Style: lifestyle-emotional (person + product)
- Disclaimer required: "For investigational use only. Not for clinical diagnosis."
- FDA guardrails: ON
- Music: warm-hopeful bed

**`helio_helioliver`** — physician-facing
- Tone: clinical, professional, evidence-based
- Style: product-focused, clean, no lifestyle imagery
- Disclaimer: regulatory + LDT language
- FDA guardrails: ON (stricter)
- Music: OFF

---

## Agent Interface (Tools to Expose)

```python
# Full ad set — primary tool
generate_ad_set(
    brief: str,
    client_id: str,                         # "helio_livertrace"
    platforms: list[str],
    product_image_url: str | None = None,
    product_url: str | None = None,         # triggers scraper
    copy_variants: int = 3,
    output_mode: str = "ad"                 # "ad" | "web_asset"
) → AdJobResult   # {platform: file_url, copy_variants, cost}

# Quick single static
generate_static(brief: str, client_id: str, platform: str) → str

# Website asset mode
generate_web_asset(page_url: str, client_id: str, brief: str | None = None) → WebAssetResult

# A/B variants
generate_variants(brief: str, client_id: str, platform: str, count: int = 3) → list[str]
```

---

## How the Marketing Agent Calls This

**Phase 1 — CLI via exec tool:**
```bash
python3 /opt/creative-pack/cli.py \
  --client helio_livertrace \
  --brief "LiverTrace DTC, warm hopeful, adults 40+, Meta Feed" \
  --platforms meta_feed meta_story google_display \
  --output /tmp/helio-creative/
```
Outputs JSON to stdout: `{"files": {...}, "cost": 0.21}`. Agent reads, delivers files via Discord attachment.

**Phase 2+ — FastAPI microservice (when second agent needs it):**
```bash
curl -s -X POST http://localhost:8001/generate \
  -H "Content-Type: application/json" \
  -d '{"client_id": "helio_livertrace", "brief": "...", "platforms": ["meta_feed"]}'
```
Run as systemd service on Helena alongside OpenClaw agents.

---

## Build Phases

### Phase 1 — Static Ads (Weeks 1–2) ← START HERE
- [ ] New GitHub repo: `wealthhealthai/creative-pack`
- [ ] Python package structure: `creative_pack/scraper.py`, `expander.py`, `assets.py`, `generator.py`, `compositor.py`, `exporter.py`, `cli.py`
- [ ] Playwright stealth setup + screenshotone fallback
- [ ] fal.ai account + API key (get from Jason if not already set)
- [ ] BiRefNet background removal
- [ ] Flux 1.1 Pro image generation (lifestyle prompt structure)
- [ ] 3 HTML/CSS ad templates: `lifestyle.html`, `product_hero.html`, `minimal.html`
- [ ] Playwright compositor renders templates at correct viewport
- [ ] Platform export (static)
- [ ] Helio brand kit JSONs for livertrace + helioliver
- [ ] `cli.py` with clean JSON stdout output
- [ ] Test: run full pipeline → 9 LiverTrace ads → send outputs to Jason for QC

**Jason reviews Phase 1 output before Phase 2 starts. Quality gate.**

### Phase 2 — Website Assets (Week 3)
- [ ] Web asset output mode
- [ ] URL → Playwright screenshot → vision model brief auto-generation
- [ ] Brand color extraction (colorthief)
- [ ] Hero format templates (desktop/mobile/OG)
- [ ] Test: scrape livertrace.com → generate improved hero

### Phase 3 — Video Ads (Weeks 4–5)
- [ ] Kling 3.0 image-to-video integration via fal.ai
- [ ] MoviePy: logo bug, text animation, CTA slide-in
- [ ] Royalty-free music bed integration
- [ ] Video platform export (9:16, 1:1, 16:9)
- [ ] Test: 3 LiverTrace video ads with music

---

## Cost Model

| Asset | API Cost to WH |
|---|---|
| Single static image | ~$0.05–0.08 |
| 9-ad set (3 copy × 3 platforms) | ~$0.15–0.25 |
| Website hero asset | ~$0.05–0.10 |
| 5-sec video ad | ~$0.20–0.30 |

Fixed infra: ~$20/mo (screenshotone). fal.ai is pure pay-per-use.

Full Helio month (~42 assets): **~$40–50 total to WH.**

---

## Questions for Jason Before Starting

1. **fal.ai API key** — does Vulcan have access, or does Jason need to provision it?
2. **screenshotone.com account** — create one or use an existing WH account?
3. **GitHub repo** — create `wealthhealthai/creative-pack` or put inside an existing repo?
4. **Helio brand assets** — need logo file (PNG with transparency), exact brand colors confirmed, any font files?
5. **HTML templates** — should Vulcan design these from scratch, or should a designer (or Jason) provide Figma/visual direction first?

---

## Full Spec

Complete technical specification:
`/Users/wealthhealth_admin/.openclaw/workspace-archon/projects/creative-pack/CREATIVE-CAPABILITY-PACK-SCOPE.md`
