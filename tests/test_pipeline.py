"""Integration test — full pipeline in mock mode (no API keys required)."""
import json
import os
import sys
import tempfile
import pytest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from creative_pack import generate_ad_set, generate_static, generate_variants


def test_full_pipeline_mock():
    """Full pipeline: brief → expand (mock) → generate (mock) → composite → files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = generate_ad_set(
            brief="LiverTrace at-home liver health test, warm hopeful tone",
            client_id="helio_livertrace",
            platforms=["meta_static"],
            copy_variants=1,
            output_dir=tmpdir,
        )

        assert result.status == "ok"
        assert len(result.files) >= 1
        assert result.job_id
        assert result.timestamp

        for key, path in result.files.items():
            assert os.path.exists(path), f"Output file missing: {path}"
            assert os.path.getsize(path) > 100, f"File too small: {path}"


def test_generate_static_returns_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = generate_static(
            brief="Test ad",
            client_id="helio_livertrace",
            platform="meta_static",
            output_dir=tmpdir,
        )
        assert path
        assert os.path.exists(path)


def test_generate_variants_count():
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = generate_variants(
            brief="Test variants",
            client_id="helio_livertrace",
            platform="meta_static",
            count=3,
            output_dir=tmpdir,
        )
        assert len(paths) == 3
        for p in paths:
            assert os.path.exists(p)


def test_multiple_platforms():
    """Test that all requested platforms produce output files."""
    platforms = ["meta_static", "google_display"]
    with tempfile.TemporaryDirectory() as tmpdir:
        result = generate_ad_set(
            brief="Test multi-platform",
            client_id="helio_livertrace",
            platforms=platforms,
            copy_variants=1,
            output_dir=tmpdir,
        )
        assert result.status == "ok"
        # Each platform × 1 variant = 2 files
        assert len(result.files) == len(platforms)


def test_helioliver_brand_kit():
    """HelioLiver physician-facing kit should also run through pipeline."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = generate_ad_set(
            brief="HelioLiver LDT physician test",
            client_id="helio_helioliver",
            platforms=["meta_static"],
            copy_variants=1,
            template="product_hero",
            output_dir=tmpdir,
        )
        assert result.status == "ok"
        assert len(result.files) >= 1


def test_cli_json_output():
    """CLI should output valid JSON."""
    import subprocess
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [
                sys.executable, "creative_pack/cli.py",
                "--client", "helio_livertrace",
                "--brief", "Test CLI",
                "--platforms", "meta_static",
                "--output", tmpdir,
                "--variants", "1",
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        assert result.returncode == 0, f"CLI failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert data["status"] == "ok"
        assert "files" in data
        assert "copy_variants" in data
