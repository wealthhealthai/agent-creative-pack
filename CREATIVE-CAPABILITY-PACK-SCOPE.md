# Creative Capability Pack — Comprehensive Scope
**Version:** 2.0 — April 22, 2026
**Author:** Archon
**Status:** Active spec — decisions locked

---

## Decisions Locked

| Decision | Choice |
|---|---|
| Deployment | Embedded into AXIA Marketing Agent (not standalone) |
| Phase order | Static ads → Website assets → Video ads |
| Image pipeline | fal.ai (Flux + BiRefNet) |
| Compositor | HTML/CSS → Playwright screenshot (see §6) |
| URL scraper | Stage 0 — Playwright stealth + screenshot/vision fallback |
| Brand consistency | Brand Kit JSON (not LoRA — too much setup friction) |
| Video audio | Music bed (Phase 3); voiceover/UGC = Phase 4 |
| Client pricing | Per-project for future clients; folded into AXIA retainer for Helio |
| Video model | Kling 3.0 Pro via fal.ai (primary) |

---

## Critical Review of v1 Spec — What Changed and Why

### ❌ Problem 1: PIL/Pillow as compositor → production quality fails

The original spec used PIL/Pillow for compositing. This is the single biggest quality risk in the pipeline. PIL's text rendering has no kerning control, no proper line-height, no text shadows, and no layout engine. For a feature whose primary value prop is "marketing production-level" output, amateur typography kills the product.

**Fix:** Replace PIL with **HTML/CSS → Playwright screenshot**.
- Full CSS layout engine: kerning, line-height, shadows, gradients, z-index
- Any Google Font in one line
- Templates are `.html` files — easy to create, version, and hand to a designer
- Same template renders 1:1, 9:16, 16:9 by resizing the Playwright viewport
- Zero marginal cost (no paid service)
- This is how professional programmatic ad tech (Google Display, Facebook dynamic ads) works under the hood

PIL stays only for simple pre-processing (crop, resize, background merge). The final compositor is Playwright.

---

### ❌ Problem 2: One output type doesn't cover all use cases

Helio has three distinct use cases:
1. **DTC static ads** — platform-constrained, CTA-driven, compliance overlay
2. **Website hero assets** — design-forward, wide format, no platform constraints, no CTA button
3. **Video ads** — cinematic, motion-first

These are meaningfully different workflows. The v1 spec treated them as one pipeline. They need separate modes.

---

### ❌ Problem 3: Copy quality was underpowered

"Brief expansion" in v1 was vague. "Marketing production-level copy" is a real bar. Generic AI copy fails it. The spec now includes:
- DTC copy frameworks baked into the LLM prompt (PAS, AIDA — see §5)
- 3 copy variants per brief (A/B/C testing built-in)
- Platform-specific character limits enforced before compositing
- For Helio: FDA guardrails injected at brief expansion (April 2026 DTC final rule applies)

---

### ❌ Problem 4: Image strategy for DTC health was wrong

Pure product shots (kit on a table) consistently underperform in DTC health advertising. Research is clear: **lifestyle/emotional imagery** (person at home, using the product, feeling relief) dramatically outperforms product-only shots. The v1 spec defaulted to product-centric generation. The updated spec prompts for person + emotion + product by default, with product-only as a variant.

This has a practical implication: Flux 1.1 Pro (people, environments) is the right model, not Flux Schnell. Faces and hands still need prompt care, but Flux 1.1 Pro handles them well.

---

### ✅ What was right in v1

- Five-stage pipeline structure (now six with URL scraper at Stage 0)
- fal.ai as infrastructure layer
- Kling 3.0 as video model
- Brand Kit as JSON config for reusability
- BiRefNet for background removal
- Platform spec dictionary pattern

---

## Helio Use Cases — Concrete Inputs and Outputs

### Use Case 1: LiverTrace DTC Static Ads

**Input:**
```
"Generate a Meta Feed ad for LiverTrace targeting adults 40+
who are concerned about liver health. Emotional hook. Clean,
trustworthy aesthetic. CTA: 'Order Your Kit Today'."
```

**Pipeline output:**
- 3 copy variants (PAS / emotional / clinical-proof)
- 3 creative directions (lifestyle shot / product close-up / abstract/metaphor)
- Composited with: LiverTrace logo, headline, body, CTA button, FDA disclaimer
- Exported in: Meta Feed (1080×1080), Meta Story (1080×1920), Google Display (1200×628)
- Total: 9 finished ad images per run

**FDA guardrails applied automatically:**
- No: "detects liver cancer", "prevents cirrhosis", "proven to improve outcomes"
- Yes: "helps assess liver health", "know your risk", "consult your physician"
- Disclaimer appended: *"LiverTrace is for investigational use only. Not for clinical diagnosis."*

---

### Use Case 2: Website Hero Asset Generation

**Input:**
```
"https://livertrace.com — improve the hero section. It feels too clinical.
We want it to feel more human and hopeful. Keep the brand colors."
```

**Pipeline:**
1. Playwright screenshots the current page (desktop + mobile)
2. Vision model analyzes current hero: colors, layout, tone, imagery style
3. LLM generates an improvement brief: "Replace stock hospital imagery with warm lifestyle scene — adult couple at home, looking at phone with relief, soft morning light, brand blue (#1A3F6F) accent"
4. Flux generates new hero background image (1920×1080)
5. Optional: composited version with text overlay placed correctly
6. Output: raw hero image + optional composited preview

**No CTA button, no disclaimer overlay** — that's the website's job. This is pure visual asset generation.

---

### Use Case 3: Video Ads (Phase 3)

**Input:**
```
"Create a 9:16 video ad for LiverTrace. Product unboxing feel.
Warm, hopeful. Music. CTA: 'Order Now'."
```

**Pipeline:**
1. Brief expansion → creative brief + motion direction
2. BiRefNet removes background from product photo
3. Flux generates lifestyle scene (person at table, soft light)
4. Kling 3.0 animates: slow camera orbit, warm light flicker
5. MoviePy composites: logo bug + headline fade in + CTA slide in + music bed
6. Export: 9:16 MP4 for TikTok/Meta Story/Reel, 1:1 for Meta Feed

---

## Pipeline Architecture — Six Stages

```
[BRIEF/URL] ─► [0. SCRAPE] ─► [1. EXPAND] ─► [2. ASSETS] ─► [3. GENERATE] ─► [4. COMPOSITE] ─► [5. EXPORT]
                  (optional)                                        │                    │
                                                           Flux / Kling           HTML/CSS→Playwright
                                                                                  (static)
                                                                                  MoviePy (video)
```

---

### Stage 0 — URL Scraper (optional, triggers Use Case 1 and 2)

Input: product or website URL
Output: `ProductAsset` — structured data for the pipeline

```python
@dataclass
class ProductAsset:
    product_name: str
    description: str
    price: str | None
    hero_images: list[str]      # URLs of all usable product images
    brand_colors: list[str]     # hex codes extracted from site
    existing_copy: str          # scraped headline/tagline
    page_screenshot_url: str    # full-page screenshot (for web asset mode)
```

**Implementation:**
```
Step 1: Playwright stealth
  → navigate to URL with real browser headers + stealth plugin
  → extract: og:image, og:title, og:description, all img[width>400], meta price
  → screenshot full page
  → extract brand colors from hero image via colorthief

Step 2 (fallback, if Step 1 blocked by Cloudflare/bot detection):
  → screenshotone.com API (handles bot detection, ~$20/mo)
  → screenshot URL returned
  → pass to Claude vision: "extract product name, description, main product image URL, primary colors"
```

Bot detection coverage: ~95% of sites handled between the two approaches.

---

### Stage 1 — Brief Expansion

Input: raw brief string + `ProductAsset` (if URL was provided) + client Brand Kit
Output: `CreativeBrief` with 3 copy variants

```python
@dataclass
class CreativeBrief:
    product_name: str
    style: str                      # "clean" | "warm" | "clinical" | "energetic"
    image_direction: str            # see §5
    copy_variants: list[CopySet]    # 3 variants
    platforms: list[str]
    output_mode: str                # "ad" | "web_asset"

@dataclass
class CopySet:
    framework: str                  # "PAS" | "AIDA" | "emotional"
    headline: str                   # platform-length enforced
    body: str
    cta: str
    disclaimer: str | None
```

**Copy framework injection (§5 below for detail):**
The LLM system prompt for brief expansion includes:
- DTC copy frameworks (PAS, AIDA) with worked examples
- Platform character limits (enforced in output schema)
- Client-specific guardrails (loaded from Brand Kit)
- Instruction to generate 3 variants: one per framework

---

### Stage 2 — Asset Preparation

**Path A (product image provided or scraped):**
1. BiRefNet background removal → clean PNG with transparency
2. If low-res: `fal-ai/esrgan` upscale to 2K
3. Product subject saved to temp store

**Path B (no image):**
1. Flux 1.1 Pro generates full scene from image direction prompt
2. For ad mode: generates lifestyle scene with person + product
3. For web asset mode: generates wide-format hero image (no compositing yet)

---

### Stage 3 — AI Generation

**Static (Ad + Web Asset):**
Model: `fal-ai/flux-pro/v1.1` — $0.04/image at 1MP
Prompt constructed from `CreativeBrief.image_direction`

**DTC health image direction strategy (critical):**
```
❌ Wrong: "LiverTrace test kit on white background"
✅ Right: "35-year-old woman at kitchen table, morning light, 
          looking at her phone with visible relief, LiverTrace 
          kit open in front of her, soft warm tones, 
          photorealistic, Canon 5D bokeh"
```
Person + emotion + context + product. Every lifestyle prompt follows this structure. Product-only is generated as a separate "product hero" variant.

**Video:**
Model: `fal-ai/kling-video/v1.6/pro/image-to-video`
- Input: lifestyle image from Stage 3 + motion prompt
- Duration: 5 seconds (cost: ~$0.15)
- Motion prompts: "slow zoom in", "gentle camera drift left", "soft focus pull"

---

### Stage 4 — Compositing

#### Static: HTML/CSS → Playwright Screenshot

Three master template types per client:
1. **`lifestyle.html`** — large background image, overlay text bottom-left, CTA button, logo top-right
2. **`product_hero.html`** — split layout: product left, copy right, CTA, logo
3. **`minimal.html`** — centered product, minimal copy above/below, clean whitespace

Each template uses CSS variables for brand colors/fonts, and data attributes for dynamic content:
```html
<div class="ad-container" 
     data-bg-image="{{ image_url }}"
     data-headline="{{ headline }}"
     data-body="{{ body }}"
     data-cta="{{ cta }}"
     data-disclaimer="{{ disclaimer }}">
```

Playwright renders at exact platform viewport → `page.screenshot(full_page=False)` → PNG.

**Why this beats PIL:**
- Web fonts (Google Fonts CDN, one line)
- `text-shadow`, `backdrop-filter`, `border-radius` — real CSS effects
- Flexbox layout = no hardcoded pixel positions
- `@media` queries for different aspect ratios — same template, different viewport
- Identical output to what a designer would produce in Figma/HTML

#### Video: MoviePy
- Logo "bug" (semi-transparent, corner, entire duration)
- Headline text: fade in at 0.5s, CSS-animated via PIL text layer
- CTA: slide in from bottom at 3.5s
- Disclaimer strip: last 2 seconds
- Music bed: royalty-free track, ducked to -15db under any generated audio

---

### Stage 5 — Platform Export

```python
PLATFORM_SPECS = {
    # Video
    "meta_feed":       {"w": 1080, "h": 1080, "ratio": "1:1",    "fmt": "mp4"},
    "meta_story":      {"w": 1080, "h": 1920, "ratio": "9:16",   "fmt": "mp4"},
    "meta_reel":       {"w": 1080, "h": 1920, "ratio": "9:16",   "fmt": "mp4"},
    "tiktok":          {"w": 1080, "h": 1920, "ratio": "9:16",   "fmt": "mp4"},
    "youtube_short":   {"w": 1080, "h": 1920, "ratio": "9:16",   "fmt": "mp4"},
    "linkedin_video":  {"w": 1920, "h": 1080, "ratio": "16:9",   "fmt": "mp4"},
    # Static
    "meta_static":     {"w": 1080, "h": 1080, "ratio": "1:1",    "fmt": "png"},
    "meta_story_img":  {"w": 1080, "h": 1920, "ratio": "9:16",   "fmt": "png"},
    "google_display":  {"w": 1200, "h": 628,  "ratio": "1.91:1", "fmt": "png"},
    "linkedin_static": {"w": 1200, "h": 627,  "ratio": "1.91:1", "fmt": "png"},
    # Web
    "hero_desktop":    {"w": 1920, "h": 1080, "ratio": "16:9",   "fmt": "jpg"},
    "hero_mobile":     {"w": 390,  "h": 844,  "ratio": "9:21",   "fmt": "jpg"},
    "hero_og":         {"w": 1200, "h": 630,  "ratio": "1.91:1", "fmt": "jpg"},
}
```

---

## Copy Quality Framework (§5)

The LLM system prompt for brief expansion uses proven DTC frameworks:

**PAS (Problem → Agitate → Solution)** — best for pain-point-driven health DTC:
```
P: "Most people don't know their liver is under stress until it's too late."
A: "By then, damage has already set in — and your doctor may not catch it."
S: "LiverTrace gives you a window into your liver health from home in minutes."
CTA: "Order Your Kit Today →"
```

**AIDA (Attention → Interest → Desire → Action)** — best for cold audiences:
```
A: "Your liver does 500 things a day. Do you know how it's doing?"
I: "LiverTrace is the first at-home liver health screening kit..."
D: "Join 10,000 people who now know their liver health status."
A: "Get yours for $99 →"
```

**Emotional/Trust** — best for retargeting:
```
"For the people who are paying attention to their health —
even when nothing feels wrong yet. LiverTrace. Know your liver."
```

**Platform character limits (enforced at output):**
| Platform | Headline | Body |
|---|---|---|
| Meta Feed | 40 chars | 125 chars |
| Meta Story | 40 chars | — (visual only) |
| Google Display | 30 chars | 90 chars |
| LinkedIn | 150 chars | 600 chars |
| TikTok | — (video text overlay only) | — |

**Helio FDA guardrails (injected into system prompt):**
- ❌ "detects", "prevents", "cures", "proven to improve", "treats"
- ✅ "helps assess", "screens for risk", "know your status", "monitor"
- Required: "consult your physician before making health decisions"
- Required: "For investigational use only. Not for clinical diagnosis." in disclaimer field
- Note: April 2026 FDA final rule on DTC broadcast ads — full fair balance required for video

---

## Brand Kit Schema

```json
{
  "client_id": "helio_livertrace",
  "product_name": "LiverTrace",
  "logo_url": "https://...",
  "logo_position": "top-right",
  "primary_color": "#1A3F6F",
  "accent_color": "#00B4D8",
  "background_color": "#FFFFFF",
  "font_headline": "Inter",
  "font_headline_weight": "700",
  "font_body": "Inter",
  "font_body_weight": "400",
  "cta_style": "rounded-pill",
  "cta_color": "#00B4D8",
  "disclaimer_required": true,
  "disclaimer_text": "For investigational use only. Not for clinical diagnosis.",
  "style_default": "warm-clinical",
  "image_style": "lifestyle-emotional",
  "fda_guardrails": true,
  "guardrail_terms_blocked": ["detects", "prevents", "cures", "treats", "proven"],
  "guardrail_terms_required": ["consult your physician"],
  "music_default": "warm-hopeful-bed.mp3"
}
```

Separate configs: `helio_livertrace.json` and `helio_helioliver.json`.
HelioLiver (physician-facing) gets: clinical tone, no lifestyle imagery, different disclaimer, no music.

---

## Agent Tools Exposed to AXIA Marketing Agent

```python
# Primary tool — full ad set from brief
generate_ad_set(
    brief: str,
    client_id: str,
    platforms: list[str],
    product_image_url: str | None = None,
    product_url: str | None = None,       # triggers URL scraper
    copy_variants: int = 3,
    output_mode: str = "ad"               # "ad" | "web_asset"
) → AdJobResult

# Quick static — single image, fastest path
generate_static(
    brief: str, client_id: str, platform: str
) → str  # file URL

# Website asset mode
generate_web_asset(
    page_url: str,
    client_id: str,
    improvement_brief: str | None = None  # optional; auto-generated if None
) → WebAssetResult

# A/B variants — multiple creative directions, same brief
generate_variants(
    brief: str, client_id: str, platform: str, count: int = 3
) → list[str]  # file URLs

# Brand kit management
get_brand_kit(client_id: str) → BrandKit
update_brand_kit(client_id: str, updates: dict) → None
```

`AdJobResult` includes: per-platform file URLs, copy variants used, API cost, generation timestamp, job ID for logging.

---

## Build Plan (Revised)

### Phase 1 — Static Ad Generation (Weeks 1–2)
- [ ] URL scraper: Playwright stealth + screenshotone fallback
- [ ] Brand kit loader for `helio_livertrace` and `helio_helioliver`
- [ ] Brief expansion: PAS/AIDA/emotional frameworks + FDA guardrails
- [ ] BiRefNet background removal pipeline
- [ ] Flux 1.1 Pro image generation (lifestyle-first prompts)
- [ ] 3 HTML/CSS ad templates per client (`lifestyle`, `product_hero`, `minimal`)
- [ ] Playwright compositor: renders templates at platform viewports
- [ ] Platform export (static formats only)
- [ ] `generate_ad_set()` and `generate_static()` tools
- [ ] Register tools in AXIA Marketing Agent
- [ ] Helio test: 9-ad set for LiverTrace (3 copy × 3 formats)

**Deliverable:** AXIA Marketing Agent can generate a full LiverTrace static ad set from a one-line brief. ~$0.15-0.25 in API costs per 9-ad set.

### Phase 2 — Website Asset Mode (Week 3)
- [ ] Web asset output mode (no CTA, no disclaimer, wide format)
- [ ] URL → screenshot → vision model brief auto-generation
- [ ] Brand color extraction from existing page
- [ ] Hero format templates (desktop 1920×1080, mobile 390×844, OG 1200×630)
- [ ] `generate_web_asset()` tool

**Deliverable:** Agent scrapes livertrace.com, generates improved hero imagery with brief auto-generated from vision analysis.

### Phase 3 — Video Ads (Weeks 4–5)
- [ ] Kling 3.0 image-to-video integration
- [ ] MoviePy compositor: logo bug, text animation layers, CTA
- [ ] Music bed: royalty-free library, auto-matched to brand tone
- [ ] Video platform export (9:16, 1:1, 16:9)
- [ ] `generate_ad_set()` updated to handle `output_type="video"`
- [ ] Helio test: 3 LiverTrace video ads

**Deliverable:** AXIA Marketing Agent generates 5-second LiverTrace video ads with music. ~$0.30-0.50 per video.

### Phase 4 — UGC/Voiceover (Future, Not Scoped Yet)
- ElevenLabs TTS voiceover
- fal.ai lipsync model for UGC-style talking head
- Intercutting product footage + avatar
- Requires separate scoping conversation

---

## Cost Model (Updated)

### Per-generation API costs (Jason's cost):

| Run | What it generates | API cost |
|---|---|---|
| Single static | 1 image, BiRefNet + Flux | ~$0.05–0.08 |
| 9-ad set (3 copy × 3 platforms) | 3 Flux images, 9 Playwright renders | ~$0.15–0.25 |
| Web asset | 1 Flux image, screenshotone if needed | ~$0.05–0.10 |
| 5-sec video | BiRefNet + Kling 3.0 | ~$0.20–0.30 |
| Full video ad set (3 platforms) | 1 Kling + 3 MoviePy renders | ~$0.25–0.40 |

### Infrastructure (monthly, fixed):
| Service | Cost | Purpose |
|---|---|---|
| fal.ai | Pay-per-use | Image + video generation |
| screenshotone.com | ~$20/mo | Bot-proof URL screenshots |
| Royalty-free music | $0–$15/mo | freemusicarchive or similar |
| **Total fixed** | **~$20–35/mo** | |

### Helio full-month estimate:
- 4 campaigns/mo × 9 static ads + 2 web assets + 3 videos = ~42 assets
- API cost: ~$15–25/month
- Fixed infra: ~$25/month
- **Total to serve Helio: ~$40–50/month**

### Future client pricing:
| Package | What they get | Price |
|---|---|---|
| Starter campaign | 9-ad static set (3 copy × 3 formats) | $500–800 |
| Full campaign | 9 static + 3 web assets + 3 videos | $1,500–2,500 |
| Monthly retainer | 2 full campaigns/mo + on-demand requests | $3,000–5,000/mo |

Gross margin at these prices: **>95%**. API costs are negligible at this volume.

---

## What Makes This Reusable (Unchanged from v1)

1. Zero hardcoded client data — everything in Brand Kit JSON
2. Model-agnostic — swap Kling for Seedance/Veo by changing one config string
3. Platform dictionary — add Pinterest/Snapchat by adding one entry
4. Output mode flag — `"ad"` vs `"web_asset"` switches the whole pipeline behavior
5. Templates are `.html` files — a designer can update them without touching Python
6. Guardrails are per-client JSON — evolve as regulatory status changes
7. Runs on any VPS or Replit — no GPU required locally

**Adding a new client:**
1. Create `brand_kits/client.json`
2. Create 3 HTML templates (copy from Helio, swap colors/fonts)
3. Done. Full pipeline works immediately.
