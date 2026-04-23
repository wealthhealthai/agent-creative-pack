"""
Stage 1 — Brief expansion: converts raw brief → structured CreativeBrief with 3 copy variants.
Uses Claude via Anthropic SDK. Falls back to mock if ANTHROPIC_API_KEY not set.
"""
import json
import re
from .models import CreativeBrief, CopySet, BrandKit, ProductAsset
from .config import ANTHROPIC_API_KEY, get_copy_limits

# ── Copy frameworks injected into system prompt ────────────────────────────
PAS_EXAMPLE = """
PAS (Problem → Agitate → Solution):
P: "Most people don't know their liver is under stress until it's too late."
A: "By then, damage has already set in — and your doctor may not catch it."
S: "LiverTrace gives you a window into your liver health from home in minutes."
CTA: "Order Your Kit Today →"
"""

AIDA_EXAMPLE = """
AIDA (Attention → Interest → Desire → Action):
A: "Your liver does 500 things a day. Do you know how it's doing?"
I: "LiverTrace is the first at-home liver health screening kit designed for everyday people."
D: "Join thousands who now know their liver health status."
A: "Get yours for $99 →"
"""

EMOTIONAL_EXAMPLE = """
Emotional/Trust (best for retargeting):
"For the people who are paying attention to their health —
even when nothing feels wrong yet.
LiverTrace. Know your liver."
CTA: "Learn More"
"""

SYSTEM_PROMPT_TEMPLATE = """
You are an expert DTC health marketing copywriter. You generate high-converting ad copy for health and wellness products.

Your output must be valid JSON matching the schema below. No markdown, no explanation — pure JSON only.

## Copy Frameworks
Generate exactly 3 variants using these frameworks:

{frameworks}

## Platform Character Limits (enforce strictly)
{limits}

## Client Guardrails
{guardrails}

## Output Schema
{{
  "product_name": "string",
  "style": "warm|clean|clinical|energetic",
  "image_direction": "string — detailed Flux prompt for lifestyle scene: person + emotion + context + product",
  "copy_variants": [
    {{
      "framework": "PAS|AIDA|emotional",
      "headline": "string (within platform limit)",
      "body": "string (within platform limit, empty string if platform has no body)",
      "cta": "string",
      "disclaimer": "string or null"
    }}
  ]
}}

Image direction rule: always follow this structure — "[age/demographic] [emotion/action] + [context/setting] + [product], [lighting], [camera], [mood]"
Example: "35-year-old woman at kitchen table, morning light, looking at phone with visible relief, LiverTrace kit open in front of her, soft warm tones, photorealistic, Canon 5D bokeh"

For physician-facing products (image_style = "product-focused"): describe a clean product shot instead of lifestyle.
"""


def _build_system_prompt(brand_kit: BrandKit, platforms: list[str]) -> str:
    # Guardrails
    blocked = ", ".join(brand_kit.guardrail_terms_blocked) or "none"
    required = ", ".join(brand_kit.guardrail_terms_required) or "none"
    disclaimer = brand_kit.disclaimer_text if brand_kit.disclaimer_required else "not required"

    guardrails = f"""
Blocked terms (never use): {blocked}
Required terms (must include): {required}
FDA guardrails active: {brand_kit.fda_guardrails}
Required disclaimer: {disclaimer}
Image style: {brand_kit.image_style}
Tone: {brand_kit.style_default}
"""

    # Copy limits for requested platforms
    limits_lines = []
    for p in platforms:
        lim = get_copy_limits(p)
        hl = lim["headline"]
        bd = lim["body"]
        limits_lines.append(f"  {p}: headline ≤{hl} chars{',' if bd else ' (no body)'}{f' body ≤{bd} chars' if bd else ''}")
    limits_str = "\n".join(limits_lines) or "  default: headline ≤80, body ≤200"

    frameworks = PAS_EXAMPLE + "\n" + AIDA_EXAMPLE + "\n" + EMOTIONAL_EXAMPLE

    return SYSTEM_PROMPT_TEMPLATE.format(
        frameworks=frameworks,
        limits=limits_str,
        guardrails=guardrails,
    )


def _mock_brief(brief: str, brand_kit: BrandKit, platforms: list[str]) -> CreativeBrief:
    """Return a mock CreativeBrief when no API key is available."""
    disclaimer = brand_kit.disclaimer_text if brand_kit.disclaimer_required else None
    product = brand_kit.product_name

    variants = [
        CopySet(
            framework="PAS",
            headline=f"Know Your {product} Risk",
            body=f"Most people don't realize {product} could change everything. Get answers at home.",
            cta="Order Your Kit Today →",
            disclaimer=disclaimer,
        ),
        CopySet(
            framework="AIDA",
            headline=f"What Is Your Liver Telling You?",
            body=f"{product} gives you clear answers about your liver health — from home, in minutes.",
            cta=f"Get {product} Now →",
            disclaimer=disclaimer,
        ),
        CopySet(
            framework="emotional",
            headline="For the people paying attention.",
            body=f"Even when nothing feels wrong yet. {product}. Know your liver.",
            cta="Learn More",
            disclaimer=disclaimer,
        ),
    ]

    # Truncate to platform limits — apply strictest limit across all requested platforms
    for v in variants:
        for p in platforms:
            lim = get_copy_limits(p)
            if lim["headline"] and len(v.headline) > lim["headline"]:
                v.headline = v.headline[:lim["headline"] - 1] + "…"
            if lim["body"] == 0:
                v.body = ""
            elif lim["body"] and len(v.body) > lim["body"]:
                v.body = v.body[:lim["body"] - 1] + "…"

    return CreativeBrief(
        product_name=product,
        style=brand_kit.style_default,
        image_direction=(
            f"35-year-old adult at home, morning light, looking at phone with visible relief, "
            f"{product} kit open in front of them, soft warm tones, photorealistic, Canon 5D bokeh"
        ),
        copy_variants=variants,
        platforms=platforms,
        output_mode="ad",
    )


def expand_brief(
    brief: str,
    brand_kit: BrandKit,
    platforms: list[str],
    product_asset: ProductAsset | None = None,
) -> CreativeBrief:
    """
    Expand a plain-language brief into a structured CreativeBrief with 3 copy variants.
    Falls back to mock output if ANTHROPIC_API_KEY is not set.
    """
    if not ANTHROPIC_API_KEY:
        print("[expander] No ANTHROPIC_API_KEY — using mock brief.")
        return _mock_brief(brief, brand_kit, platforms)

    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
    except ImportError:
        print("[expander] anthropic package not installed — using mock brief.")
        return _mock_brief(brief, brand_kit, platforms)

    # Build context from product asset if available
    product_context = ""
    if product_asset:
        product_context = f"""
Product context (scraped):
- Name: {product_asset.product_name}
- Description: {product_asset.description}
- Existing copy: {product_asset.existing_copy}
"""

    user_message = f"""
Client: {brand_kit.client_id}
Product: {brand_kit.product_name}
Brief: {brief}
Target platforms: {', '.join(platforms)}
{product_context}

Generate the CreativeBrief JSON with 3 copy variants (PAS, AIDA, emotional).
"""

    system = _build_system_prompt(brand_kit, platforms)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text.strip()

    # Strip markdown fences if present
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    data = json.loads(raw)

    variants = [
        CopySet(
            framework=v["framework"],
            headline=v["headline"],
            body=v.get("body", ""),
            cta=v["cta"],
            disclaimer=v.get("disclaimer"),
        )
        for v in data["copy_variants"]
    ]

    return CreativeBrief(
        product_name=data["product_name"],
        style=data["style"],
        image_direction=data["image_direction"],
        copy_variants=variants,
        platforms=platforms,
        output_mode="ad",
    )
