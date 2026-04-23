"""
Stage 1 — Brief Expansion
==========================
Converts a raw user brief into a structured CreativeBrief with 3 copy variants
(PAS, AIDA, emotional) using Claude claude-opus-4-5.

Falls back to mock copy if ANTHROPIC_API_KEY is not set.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from creative_pack.models import BrandKit, CopySet, CreativeBrief, ProductAsset
from creative_pack.config import ANTHROPIC_API_KEY, get_copy_limits


# ---------------------------------------------------------------------------
# Copy framework examples (injected into system prompt)
# ---------------------------------------------------------------------------

_PAS_EXAMPLE = """
PAS (Problem → Agitate → Solution) — best for pain-point-driven health DTC:
  Headline: "Most people don't know their liver is under stress until it's too late."
  Body: "By then, damage has already set in — and your doctor may not catch it. LiverTrace gives you a window into your liver health from home in minutes."
  CTA: "Order Your Kit Today →"
""".strip()

_AIDA_EXAMPLE = """
AIDA (Attention → Interest → Desire → Action) — best for cold audiences:
  Headline: "Your liver does 500 things a day. Do you know how it's doing?"
  Body: "LiverTrace is the first at-home liver health screening kit. Join 10,000 people who now know their liver health status."
  CTA: "Get yours for $99 →"
""".strip()

_EMOTIONAL_EXAMPLE = """
Emotional/Trust — best for retargeting and brand awareness:
  Headline: "For people paying attention to their health."
  Body: "Even when nothing feels wrong yet. LiverTrace. Know your liver."
  CTA: "Learn More"
""".strip()

_FDA_INSTRUCTIONS = """
CRITICAL FDA GUARDRAILS (April 2026 DTC Final Rule):
  BLOCKED terms — never use: detects, prevents, cures, treats, proven to improve, proven to reduce
  REQUIRED phrase: include "consult your physician before making health decisions" in body or disclaimer
  REQUIRED disclaimer: "For investigational use only. Not for clinical diagnosis."
  USE instead of blocked terms: "helps assess", "screens for risk", "know your status", "monitor"
""".strip()


def _build_system_prompt(brand_kit: BrandKit, platforms: list[str]) -> str:
    """Construct the LLM system prompt for brief expansion."""
    # Copy limits for the first target platform
    primary_platform = platforms[0] if platforms else "meta_static"
    limits = get_copy_limits(primary_platform)
    hl_limit = limits.get("headline") or 150
    body_limit = limits.get("body") or 600

    guardrails_blocked = ", ".join(brand_kit.guardrail_terms_blocked) or "none"
    guardrails_required = ", ".join(brand_kit.guardrail_terms_required) or "none"

    fda_section = _FDA_INSTRUCTIONS if brand_kit.fda_guardrails else ""

    prompt = f"""You are an expert DTC healthcare copywriter generating digital ad creative.

PRODUCT: {brand_kit.product_name}
CLIENT STYLE: {brand_kit.style_default}
IMAGE STYLE: {brand_kit.image_style}
TARGET PLATFORMS: {", ".join(platforms)}

CHARACTER LIMITS (strictly enforce):
  Headline: max {hl_limit} characters
  Body: max {body_limit} characters (None = no body text for this platform)

CLIENT GUARDRAILS:
  Blocked terms: {guardrails_blocked}
  Required terms: {guardrails_required}

{fda_section}

COPY FRAMEWORKS:

{_PAS_EXAMPLE}

{_AIDA_EXAMPLE}

{_EMOTIONAL_EXAMPLE}

IMAGE DIRECTION STRATEGY:
  For lifestyle/emotional style: describe a real person in an emotional scene with the product.
  Format: "[person description] + [emotion/feeling] + [context/setting] + [product], [lighting], [camera style]"
  Example: "35-year-old woman at kitchen table, morning light, looking at her phone with visible relief, LiverTrace kit open in front of her, soft warm tones, photorealistic, Canon 5D bokeh"

  For clinical/product-focused style: product-only shot, clean, clinical, professional.
  Example: "LiverTrace kit on clean white surface, clinical lighting, professional product photography"

OUTPUT FORMAT (strict JSON, no markdown):
{{
  "product_name": "...",
  "style": "warm|clean|clinical|energetic",
  "image_direction": "...",
  "output_mode": "ad",
  "copy_variants": [
    {{
      "framework": "PAS",
      "headline": "...",
      "body": "...",
      "cta": "...",
      "disclaimer": "..." or null
    }},
    {{
      "framework": "AIDA",
      "headline": "...",
      "body": "...",
      "cta": "...",
      "disclaimer": "..." or null
    }},
    {{
      "framework": "emotional",
      "headline": "...",
      "body": "...",
      "cta": "...",
      "disclaimer": "..." or null
    }}
  ]
}}

Generate exactly 3 copy variants: PAS, AIDA, emotional.
All text must stay within character limits.
All blocked terms must be absent. All required terms must appear.
If fda_guardrails is true, include the full disclaimer in every variant's disclaimer field.
"""
    return prompt.strip()


def _enforce_char_limits(copy_set: CopySet, platform: str) -> CopySet:
    """Truncate headline and body to platform character limits."""
    limits = get_copy_limits(platform)
    hl_limit = limits.get("headline")
    body_limit = limits.get("body")

    headline = copy_set.headline
    body = copy_set.body

    if hl_limit and len(headline) > hl_limit:
        headline = headline[: hl_limit - 1].rstrip() + "…"
    if body_limit and body and len(body) > body_limit:
        body = body[: body_limit - 1].rstrip() + "…"

    return CopySet(
        framework=copy_set.framework,
        headline=headline,
        body=body,
        cta=copy_set.cta,
        disclaimer=copy_set.disclaimer,
    )


def _mock_brief(
    brief: str,
    brand_kit: BrandKit,
    platforms: list[str],
    product_asset: Optional[ProductAsset],
) -> CreativeBrief:
    """Return a mock CreativeBrief when no API key is available."""
    product_name = brand_kit.product_name
    if product_asset and product_asset.product_name:
        product_name = product_asset.product_name

    disclaimer = brand_kit.disclaimer_text if brand_kit.disclaimer_required else None

    primary_platform = platforms[0] if platforms else "meta_static"
    limits = get_copy_limits(primary_platform)
    hl_limit = limits.get("headline") or 150
    body_limit = limits.get("body") or 600

    def trim(text: str, limit: Optional[int]) -> str:
        if limit and len(text) > limit:
            return text[: limit - 1].rstrip() + "…"
        return text

    pas_hl = trim(f"Most people don't know their liver is at risk.", hl_limit)
    pas_body = trim(
        f"Damage sets in silently. {product_name} gives you a window into your liver health from home. "
        "Consult your physician before making health decisions.",
        body_limit,
    )

    aida_hl = trim(f"Your liver does 500 things a day. Do you know how it's doing?", hl_limit)
    aida_body = trim(
        f"{product_name} is the first at-home liver health screening kit. "
        "Consult your physician before making health decisions.",
        body_limit,
    )

    emo_hl = trim(f"For people paying attention to their health.", hl_limit)
    emo_body = trim(
        f"Even when nothing feels wrong yet. {product_name} — know your liver. "
        "Consult your physician before making health decisions.",
        body_limit,
    )

    return CreativeBrief(
        product_name=product_name,
        style=brand_kit.style_default,
        image_direction=(
            f"35-year-old adult at kitchen table, morning light, looking at phone with relief, "
            f"{product_name} kit open in front of them, soft warm tones, photorealistic"
        ),
        copy_variants=[
            CopySet(
                framework="PAS",
                headline=pas_hl,
                body=pas_body,
                cta="Order Your Kit Today →",
                disclaimer=disclaimer,
            ),
            CopySet(
                framework="AIDA",
                headline=aida_hl,
                body=aida_body,
                cta=f"Get Yours →",
                disclaimer=disclaimer,
            ),
            CopySet(
                framework="emotional",
                headline=emo_hl,
                body=emo_body,
                cta="Learn More",
                disclaimer=disclaimer,
            ),
        ],
        platforms=platforms,
        output_mode="ad",
    )


def expand_brief(
    brief: str,
    brand_kit: BrandKit,
    platforms: list[str],
    product_asset: Optional[ProductAsset] = None,
) -> CreativeBrief:
    """
    Stage 1: Expand a raw brief into a structured CreativeBrief.

    Uses Claude claude-opus-4-5 if ANTHROPIC_API_KEY is set, otherwise returns
    a mock brief with placeholder copy.
    """
    if not ANTHROPIC_API_KEY:
        print("[expander] No ANTHROPIC_API_KEY — returning mock brief", file=__import__('sys').stderr)
        return _mock_brief(brief, brand_kit, platforms, product_asset)

    try:
        from anthropic import Anthropic

        client = Anthropic()
        system_prompt = _build_system_prompt(brand_kit, platforms)

        # Build user message
        user_parts = [f"Brief: {brief}"]
        if product_asset:
            user_parts.append(f"Product name: {product_asset.product_name}")
            if product_asset.description:
                user_parts.append(f"Product description: {product_asset.description}")
            if product_asset.existing_copy:
                user_parts.append(f"Existing tagline: {product_asset.existing_copy}")
            if product_asset.price:
                user_parts.append(f"Price: {product_asset.price}")
        user_message = "\n".join(user_parts)

        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        raw = response.content[0].text
        # Strip markdown code blocks if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        raw = re.sub(r"\s*```$", "", raw)

        data = json.loads(raw)

        copy_variants: list[CopySet] = []
        primary_platform = platforms[0] if platforms else "meta_static"
        for cv in data.get("copy_variants", []):
            cs = CopySet(
                framework=cv.get("framework", "unknown"),
                headline=cv.get("headline", ""),
                body=cv.get("body", ""),
                cta=cv.get("cta", "Learn More"),
                disclaimer=cv.get("disclaimer"),
            )
            # Enforce character limits
            cs = _enforce_char_limits(cs, primary_platform)
            copy_variants.append(cs)

        # Ensure exactly 3 variants
        while len(copy_variants) < 3:
            mock = _mock_brief(brief, brand_kit, platforms, product_asset)
            copy_variants.append(mock.copy_variants[len(copy_variants)])

        return CreativeBrief(
            product_name=data.get("product_name", brand_kit.product_name),
            style=data.get("style", brand_kit.style_default),
            image_direction=data.get("image_direction", ""),
            copy_variants=copy_variants[:3],
            platforms=platforms,
            output_mode=data.get("output_mode", "ad"),
        )

    except Exception as e:
        print(f"[expander] Claude API error: {e} — falling back to mock", file=__import__('sys').stderr)
        return _mock_brief(brief, brand_kit, platforms, product_asset)
