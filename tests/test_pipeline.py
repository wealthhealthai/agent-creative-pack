"""
test_pipeline.py
================
Integration test: runs the full pipeline from brief → output files.
No API keys required — everything runs in mock mode.
Verifies the output directory contains the expected files.
"""

import json
import os
import subprocess
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_valid_png(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(8) == b"\x89PNG\r\n\x1a\n"
    except Exception:
        return False


def _count_png_files(directory: str) -> int:
    count = 0
    for root, _, files in os.walk(directory):
        for fname in files:
            if fname.lower().endswith(".png"):
                count += 1
    return count


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

def test_full_pipeline_single_platform():
    """Run generate_ad_set for a single platform — should produce at least 1 PNG."""
    os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ.pop("FAL_API_KEY", None)

    from creative_pack import generate_ad_set

    output_dir = tempfile.mkdtemp(prefix="cp_test_pipeline_")
    result = generate_ad_set(
        brief="LiverTrace DTC, warm hopeful, adults 40+",
        client_id="helio_livertrace",
        platforms=["meta_static"],
        copy_variants=1,
        output_dir=output_dir,
    )

    assert result is not None
    assert isinstance(result.files, dict)
    assert len(result.files) >= 1, f"Expected at least 1 file, got {result.files}"

    # All file values should point to existing files
    for platform_key, file_path in result.files.items():
        assert os.path.exists(file_path), f"File not found: {file_path} (key: {platform_key})"
        assert _is_valid_png(file_path), f"File is not valid PNG: {file_path}"


def test_full_pipeline_three_platforms():
    """Run generate_ad_set for 3 platforms with 1 variant — should produce 3 files."""
    os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ.pop("FAL_API_KEY", None)

    from creative_pack import generate_ad_set

    output_dir = tempfile.mkdtemp(prefix="cp_test_pipeline_3p_")
    platforms = ["meta_static", "meta_story_img", "google_display"]

    result = generate_ad_set(
        brief="Test pipeline three platforms",
        client_id="helio_livertrace",
        platforms=platforms,
        copy_variants=1,
        output_dir=output_dir,
    )

    assert len(result.files) >= len(platforms), (
        f"Expected at least {len(platforms)} files, got {len(result.files)}: {list(result.files.keys())}"
    )

    for file_path in result.files.values():
        assert os.path.exists(file_path)
        assert _is_valid_png(file_path)


def test_full_pipeline_three_variants():
    """3 variants × 1 platform = 3 output files."""
    os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ.pop("FAL_API_KEY", None)

    from creative_pack import generate_ad_set

    output_dir = tempfile.mkdtemp(prefix="cp_test_pipeline_3v_")

    result = generate_ad_set(
        brief="Test pipeline three variants",
        client_id="helio_livertrace",
        platforms=["meta_static"],
        copy_variants=3,
        output_dir=output_dir,
    )

    assert len(result.files) == 3, (
        f"Expected 3 files (one per variant), got {len(result.files)}"
    )
    assert len(result.copy_variants) == 3


def test_full_pipeline_mock_cost_is_zero():
    """When FAL_API_KEY is not set, cost should be 0.0."""
    os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ.pop("FAL_API_KEY", None)

    from creative_pack import generate_ad_set

    output_dir = tempfile.mkdtemp(prefix="cp_test_pipeline_cost_")

    result = generate_ad_set(
        brief="Cost test",
        client_id="helio_livertrace",
        platforms=["meta_static"],
        copy_variants=1,
        output_dir=output_dir,
    )

    assert result.cost == 0.0, f"Expected cost 0.0 in mock mode, got {result.cost}"


def test_full_pipeline_result_has_job_id_and_timestamp():
    """AdJobResult must have a job_id and ISO timestamp."""
    os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ.pop("FAL_API_KEY", None)

    from creative_pack import generate_ad_set

    output_dir = tempfile.mkdtemp(prefix="cp_test_pipeline_meta_")

    result = generate_ad_set(
        brief="Metadata test",
        client_id="helio_livertrace",
        platforms=["meta_static"],
        copy_variants=1,
        output_dir=output_dir,
    )

    assert result.job_id, "job_id must not be empty"
    assert result.timestamp, "timestamp must not be empty"
    # Basic ISO timestamp check
    assert "T" in result.timestamp, f"Timestamp doesn't look like ISO: {result.timestamp}"


def test_full_pipeline_helioliver_brand_kit():
    """Pipeline should work with the helio_helioliver (physician-facing) brand kit."""
    os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ.pop("FAL_API_KEY", None)

    from creative_pack import generate_ad_set

    output_dir = tempfile.mkdtemp(prefix="cp_test_pipeline_hlo_")

    result = generate_ad_set(
        brief="HelioLiver LDT for hepatologists",
        client_id="helio_helioliver",
        platforms=["meta_static"],
        copy_variants=1,
        output_dir=output_dir,
    )

    assert len(result.files) >= 1
    for file_path in result.files.values():
        assert os.path.exists(file_path)


def test_cli_mock_mode_json_output():
    """Run CLI in mock mode — stdout should be valid JSON with status=ok."""
    os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ.pop("FAL_API_KEY", None)

    output_dir = tempfile.mkdtemp(prefix="cp_test_cli_")

    cli_path = os.path.join(
        os.path.dirname(__file__), "..", "creative_pack", "cli.py"
    )

    result = subprocess.run(
        [
            sys.executable,
            cli_path,
            "--client", "helio_livertrace",
            "--brief", "CLI integration test",
            "--platforms", "meta_static",
            "--output", output_dir,
            "--variants", "1",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        env={**os.environ},
    )

    assert result.returncode == 0, (
        f"CLI exited with code {result.returncode}.\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    )

    # Parse JSON output
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        pytest.fail(f"CLI output is not valid JSON: {e}\nOutput: {result.stdout}")

    assert data.get("status") == "ok", f"Expected status=ok, got: {data}"
    assert "files" in data, "JSON missing 'files' key"
    assert "cost" in data, "JSON missing 'cost' key"
    assert "copy_variants" in data, "JSON missing 'copy_variants' key"

    # Verify file(s) exist
    for platform_key, file_path in data["files"].items():
        assert os.path.exists(file_path), f"CLI reported file not found: {file_path}"
