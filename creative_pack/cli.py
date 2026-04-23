"""
Creative Pack CLI
=================
Run the full static ad pipeline from the command line.

Usage:
    python3 creative_pack/cli.py \\
        --client helio_livertrace \\
        --brief "LiverTrace DTC, warm hopeful, adults 40+" \\
        --platforms meta_static meta_story_img google_display \\
        --output /tmp/creative-out/

Output (stdout):
    {
        "status": "ok",
        "files": {"meta_static_v1": "/tmp/creative-out/.../meta_static_xxx.png"},
        "cost": 0.0,
        "copy_variants": [...],
        "job_id": "abc12345"
    }

On error:
    {"status": "error", "message": "..."}
"""

from __future__ import annotations

import argparse
import json
import sys
import os


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="creative-pack",
        description="Generate production-quality digital ad creative from a brief.",
    )
    parser.add_argument(
        "--client",
        required=True,
        help="Client ID matching a brand kit (e.g. helio_livertrace)",
    )
    parser.add_argument(
        "--brief",
        required=True,
        help="One-line creative brief for copy and image direction",
    )
    parser.add_argument(
        "--platforms",
        nargs="+",
        default=["meta_static"],
        help="Platform(s) to generate for (space-separated)",
    )
    parser.add_argument(
        "--output",
        default="/tmp/creative-pack-output/",
        help="Output directory for generated files",
    )
    parser.add_argument(
        "--product-url",
        default=None,
        dest="product_url",
        help="Optional product/website URL to scrape for additional context",
    )
    parser.add_argument(
        "--product-image",
        default=None,
        dest="product_image_url",
        help="Optional product image URL for background removal",
    )
    parser.add_argument(
        "--variants",
        type=int,
        default=3,
        help="Number of copy variants to generate (1-3)",
    )
    parser.add_argument(
        "--mode",
        default="ad",
        choices=["ad", "web_asset"],
        help="Output mode",
    )

    args = parser.parse_args()

    # Add project root to path so imports work when running as script
    _here = os.path.dirname(os.path.abspath(__file__))
    _root = os.path.dirname(_here)
    if _root not in sys.path:
        sys.path.insert(0, _root)

    try:
        from creative_pack import generate_ad_set

        result = generate_ad_set(
            brief=args.brief,
            client_id=args.client,
            platforms=args.platforms,
            product_image_url=args.product_image_url,
            product_url=args.product_url,
            copy_variants=args.variants,
            output_mode=args.mode,
            output_dir=args.output,
        )

        output = {
            "status": "ok",
            "files": result.files,
            "cost": result.cost,
            "job_id": result.job_id,
            "timestamp": result.timestamp,
            "copy_variants": [cv.to_dict() for cv in result.copy_variants],
        }
        print(json.dumps(output, indent=2))

    except FileNotFoundError as e:
        print(json.dumps({"status": "error", "message": str(e)}))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"status": "error", "message": repr(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
