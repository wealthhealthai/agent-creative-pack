#!/usr/bin/env python3
"""
CLI entrypoint for agent-creative-pack.
Outputs JSON to stdout. All errors also go to stdout as {"status": "error", ...}.

Usage:
  python3 cli.py \\
    --client helio_livertrace \\
    --brief "LiverTrace DTC, warm hopeful, adults 40+" \\
    --platforms meta_static meta_story_img google_display \\
    --output /tmp/creative-out/
"""
import argparse
import json
import sys
import traceback
from pathlib import Path

# Allow running as `python3 creative_pack/cli.py` from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from creative_pack import generate_ad_set
from creative_pack.models import CopySet


def main():
    parser = argparse.ArgumentParser(description="Generate ad creative from a brief.")
    parser.add_argument("--client", required=True, help="Client brand kit ID (e.g. helio_livertrace)")
    parser.add_argument("--brief", required=True, help="Plain-language creative brief")
    parser.add_argument("--platforms", nargs="+", required=True,
                        help="Target platforms (e.g. meta_static meta_story_img google_display)")
    parser.add_argument("--output", default=None, help="Output directory (default: ./output/<job_id>)")
    parser.add_argument("--template", default="lifestyle",
                        choices=["lifestyle", "product_hero", "minimal"],
                        help="Ad template to use (default: lifestyle)")
    parser.add_argument("--variants", type=int, default=3, help="Number of copy variants (1-3)")
    parser.add_argument("--product-image", default=None, help="Product image URL for bg removal")
    parser.add_argument("--product-url", default=None, help="Product page URL to scrape")
    parser.add_argument("--model", default=None,
                        choices=["flux-pro", "flux-ultra", "recraft-v3", "nano-banana-pro"],
                        help="Image generation model (default: flux-pro)")

    args = parser.parse_args()

    # Redirect all pipeline debug prints to stderr so stdout stays clean JSON
    import builtins
    _orig_print = builtins.print
    def _stderr_print(*args, **kwargs):
        kwargs.setdefault("file", sys.stderr)
        _orig_print(*args, **kwargs)
    builtins.print = _stderr_print

    try:
        result = generate_ad_set(
            brief=args.brief,
            client_id=args.client,
            platforms=args.platforms,
            product_image_url=args.product_image,
            product_url=args.product_url,
            copy_variants=min(args.variants, 3),
            template=args.template,
            output_dir=args.output,
            model=args.model,
        )

        # Serialize copy variants
        variants_out = [
            {
                "framework": v.framework,
                "headline": v.headline,
                "body": v.body,
                "cta": v.cta,
                "disclaimer": v.disclaimer,
            }
            for v in result.copy_variants
        ]

        output = {
            "status": "ok",
            "job_id": result.job_id,
            "timestamp": result.timestamp,
            "files": result.files,
            "copy_variants": variants_out,
            "cost": result.cost,
            "mock_mode": not bool(__import__("os").environ.get("FAL_API_KEY")),
        }
        builtins.print = _orig_print
        print(json.dumps(output, indent=2))

    except FileNotFoundError as e:
        builtins.print = _orig_print
        print(json.dumps({"status": "error", "message": str(e)}))
        sys.exit(1)
    except Exception as e:
        builtins.print = _orig_print
        print(json.dumps({
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc(),
        }))
        sys.exit(1)


if __name__ == "__main__":
    main()
