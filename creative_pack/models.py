"""
Dataclasses for the Creative Capability Pack pipeline.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CopySet:
    framework: str          # "PAS" | "AIDA" | "emotional"
    headline: str
    body: str
    cta: str
    disclaimer: Optional[str] = None


@dataclass
class CreativeBrief:
    product_name: str
    style: str              # "clean" | "warm" | "clinical" | "energetic"
    image_direction: str    # Flux prompt for the lifestyle/hero scene
    copy_variants: list[CopySet] = field(default_factory=list)
    platforms: list[str] = field(default_factory=list)
    output_mode: str = "ad"  # "ad" | "web_asset"


@dataclass
class BrandKit:
    client_id: str
    product_name: str
    logo_url: str
    logo_position: str
    primary_color: str
    accent_color: str
    background_color: str
    font_headline: str
    font_headline_weight: str
    font_body: str
    font_body_weight: str
    cta_style: str
    cta_color: str
    disclaimer_required: bool
    disclaimer_text: str
    style_default: str
    image_style: str
    fda_guardrails: bool
    guardrail_terms_blocked: list[str] = field(default_factory=list)
    guardrail_terms_required: list[str] = field(default_factory=list)
    music_default: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "BrandKit":
        return cls(
            client_id=d["client_id"],
            product_name=d["product_name"],
            logo_url=d.get("logo_url", ""),
            logo_position=d.get("logo_position", "top-right"),
            primary_color=d.get("primary_color", "#000000"),
            accent_color=d.get("accent_color", "#0066CC"),
            background_color=d.get("background_color", "#FFFFFF"),
            font_headline=d.get("font_headline", "Inter"),
            font_headline_weight=d.get("font_headline_weight", "700"),
            font_body=d.get("font_body", "Inter"),
            font_body_weight=d.get("font_body_weight", "400"),
            cta_style=d.get("cta_style", "rounded-pill"),
            cta_color=d.get("cta_color", "#0066CC"),
            disclaimer_required=d.get("disclaimer_required", False),
            disclaimer_text=d.get("disclaimer_text", ""),
            style_default=d.get("style_default", "clean"),
            image_style=d.get("image_style", "lifestyle-emotional"),
            fda_guardrails=d.get("fda_guardrails", False),
            guardrail_terms_blocked=d.get("guardrail_terms_blocked", []),
            guardrail_terms_required=d.get("guardrail_terms_required", []),
            music_default=d.get("music_default"),
        )


@dataclass
class ProductAsset:
    product_name: str
    description: str
    price: Optional[str] = None
    hero_images: list[str] = field(default_factory=list)
    brand_colors: list[str] = field(default_factory=list)
    existing_copy: str = ""
    page_screenshot_url: str = ""


@dataclass
class AdJobResult:
    files: dict        # platform -> local file path
    copy_variants: list[CopySet]
    cost: float
    job_id: str
    timestamp: str
    status: str = "ok"


@dataclass
class WebAssetResult:
    files: dict        # format -> local file path
    improvement_brief: str
    cost: float
    job_id: str
    timestamp: str
