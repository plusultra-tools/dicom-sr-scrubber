"""Tests for cli module."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from dicom_sr_scrubber.cli import _collect_inputs, main
from tests.conftest import build_synthetic_sr


def _write_synthetic_sr(out_path: Path) -> None:
    """Write a synthetic SR DICOM file to disk for CLI tests."""
    ds = build_synthetic_sr()
    ds.save_as(str(out_path), write_like_original=False)


class TestCollectInputs:
    def test_single_file(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".dcm", delete=False) as f:
            p = Path(f.name)
        try:
            _write_synthetic_sr(p)
            result = _collect_inputs(str(p))
            assert len(result) == 1
            assert result[0] == p
        finally:
            p.unlink(missing_ok=True)

    def test_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            for i in range(3):
                _write_synthetic_sr(d / f"sr_{i}.dcm")
            result = _collect_inputs(tmpdir)
            assert len(result) == 3

    def test_missing_file_skipped(self) -> None:
        result = _collect_inputs("/nonexistent/path/file.dcm")
        assert result == []


class TestMain:
    def test_runs_successfully(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            in_dir = Path(tmpdir) / "in"
            out_dir = Path(tmpdir) / "out"
            in_dir.mkdir()
            _write_synthetic_sr(in_dir / "sr.dcm")
            rc = main(["--input", str(in_dir), "--out", str(out_dir)])
            assert rc == 0
            assert (out_dir / "sr_evidence.json").exists()
            assert (out_dir / "audit.sha256").exists()

    def test_dry_run_no_dicom_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            in_dir = Path(tmpdir) / "in"
            out_dir = Path(tmpdir) / "out"
            in_dir.mkdir()
            _write_synthetic_sr(in_dir / "sr.dcm")
            rc = main([
                "--input", str(in_dir),
                "--out", str(out_dir),
                "--dry-run",
            ])
            assert rc == 0
            # No scrubbed DICOM in output
            assert not (out_dir / "sr.dcm").exists()
            # But manifest IS written
            assert (out_dir / "sr_evidence.json").exists()

    def test_conservative_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            in_dir = Path(tmpdir) / "in"
            out_dir = Path(tmpdir) / "out"
            in_dir.mkdir()
            _write_synthetic_sr(in_dir / "sr.dcm")
            rc = main([
                "--input", str(in_dir),
                "--out", str(out_dir),
                "--profile", "conservative",
            ])
            assert rc == 0

    def test_no_input_returns_nonzero(self) -> None:
        rc = main(["--input", "/nonexistent/file.dcm", "--out", "/tmp/out"])
        assert rc != 0

    def test_version_flag(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])
        assert exc_info.value.code == 0

    def test_blacklist_option(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            in_dir = Path(tmpdir) / "in"
            out_dir = Path(tmpdir) / "out"
            in_dir.mkdir()
            _write_synthetic_sr(in_dir / "sr.dcm")
            rc = main([
                "--input", str(in_dir),
                "--out", str(out_dir),
                "--blacklist", "JohnDoe,TestPatient",
            ])
            assert rc == 0

    def test_continue_on_error_with_corrupt_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            in_dir = Path(tmpdir) / "in"
            out_dir = Path(tmpdir) / "out"
            in_dir.mkdir()
            # Write a corrupt (non-DICOM) file
            corrupt = in_dir / "bad.dcm"
            corrupt.write_bytes(b"NOT_A_DICOM_FILE\x00" * 16)
            rc = main([
                "--input", str(in_dir),
                "--out", str(out_dir),
                "--continue-on-error",
            ])
            # Should not crash, manifest still written
            assert rc == 0
