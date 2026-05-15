"""Tests for scrubber module."""
from __future__ import annotations

import re

import pydicom

from dicom_sr_scrubber.profiles import get_profile
from dicom_sr_scrubber.scrubber import ScrubOptions, scrub_dataset
from dicom_sr_scrubber.sr_walker import get_value_type, iter_content_items


def _get_all_text_values(ds: pydicom.FileDataset) -> list[str]:
    """Collect all TextValue strings from the SR content tree."""
    values: list[str] = []
    for _, item in iter_content_items(ds):
        if get_value_type(item) == "TEXT":
            elem = item.get((0x0040, 0xA160))
            if elem is not None:
                values.append(str(elem.value))
    return values


def _get_all_pname_values(ds: pydicom.FileDataset) -> list[str]:
    values: list[str] = []
    for _, item in iter_content_items(ds):
        if get_value_type(item) == "PNAME":
            elem = item.get((0x0040, 0xA123))
            if elem is not None:
                values.append(str(elem.value))
    return values


def _get_all_date_values(ds: pydicom.FileDataset) -> list[str]:
    values: list[str] = []
    for _, item in iter_content_items(ds):
        if get_value_type(item) == "DATE":
            elem = item.get((0x0040, 0xA121))
            if elem is not None:
                values.append(str(elem.value))
    return values


def _get_all_time_values(ds: pydicom.FileDataset) -> list[str]:
    values: list[str] = []
    for _, item in iter_content_items(ds):
        if get_value_type(item) == "TIME":
            elem = item.get((0x0040, 0xA122))
            if elem is not None:
                values.append(str(elem.value))
    return values


class TestScrubDatasetDefault:
    def test_phi_text_is_redacted(self, synthetic_sr: pydicom.FileDataset) -> None:
        profile = get_profile("default")
        options = ScrubOptions()
        scrubbed, _manifest = scrub_dataset(synthetic_sr, profile, options)
        text_values = _get_all_text_values(scrubbed)
        # SSN should be gone
        for v in text_values:
            assert re.search(r"\d{3}-\d{2}-\d{4}", v) is None, (
                f"SSN still in text value: {v!r}"
            )

    def test_email_in_nested_container_is_redacted(
        self, synthetic_sr: pydicom.FileDataset
    ) -> None:
        profile = get_profile("default")
        options = ScrubOptions()
        scrubbed, _manifest = scrub_dataset(synthetic_sr, profile, options)
        text_values = _get_all_text_values(scrubbed)
        for v in text_values:
            assert "test@example.com" not in v, f"Email still present: {v!r}"

    def test_clean_text_is_kept(self, synthetic_sr: pydicom.FileDataset) -> None:
        profile = get_profile("default")
        options = ScrubOptions()
        scrubbed, _manifest = scrub_dataset(synthetic_sr, profile, options)
        text_values = _get_all_text_values(scrubbed)
        assert any("No abnormalities detected" in v for v in text_values), (
            "Clean text was incorrectly removed"
        )

    def test_pname_is_replaced(self, synthetic_sr: pydicom.FileDataset) -> None:
        profile = get_profile("default")
        options = ScrubOptions()
        scrubbed, _manifest = scrub_dataset(synthetic_sr, profile, options)
        pname_values = _get_all_pname_values(scrubbed)
        for v in pname_values:
            assert "Radiologist" not in v, f"Original PNAME still present: {v!r}"

    def test_date_is_generalised(self, synthetic_sr: pydicom.FileDataset) -> None:
        profile = get_profile("default")
        options = ScrubOptions()
        scrubbed, _manifest = scrub_dataset(synthetic_sr, profile, options)
        date_values = _get_all_date_values(scrubbed)
        for v in date_values:
            # Year only: ends with 0101
            assert v.endswith("0101"), f"Date not generalised to year-only: {v!r}"

    def test_time_is_zeroed(self, synthetic_sr: pydicom.FileDataset) -> None:
        profile = get_profile("default")
        options = ScrubOptions()
        scrubbed, _manifest = scrub_dataset(synthetic_sr, profile, options)
        time_values = _get_all_time_values(scrubbed)
        for v in time_values:
            assert v == "000000.000000", f"Time not zeroed: {v!r}"

    def test_header_patient_name_is_anonymised(
        self, synthetic_sr: pydicom.FileDataset
    ) -> None:
        profile = get_profile("default")
        options = ScrubOptions()
        scrubbed, _manifest = scrub_dataset(synthetic_sr, profile, options)
        assert "Doe" not in str(scrubbed.PatientName), (
            f"Patient name not anonymised: {scrubbed.PatientName!r}"
        )

    def test_header_referring_physician_anonymised(
        self, synthetic_sr: pydicom.FileDataset
    ) -> None:
        profile = get_profile("default")
        options = ScrubOptions()
        scrubbed, _manifest = scrub_dataset(synthetic_sr, profile, options)
        assert "Smith" not in str(scrubbed.ReferringPhysicianName)

    def test_manifest_has_entries(self, synthetic_sr: pydicom.FileDataset) -> None:
        profile = get_profile("default")
        options = ScrubOptions()
        _, manifest = scrub_dataset(synthetic_sr, profile, options)
        assert len(manifest.entries) > 0

    def test_manifest_has_redact_entries(
        self, synthetic_sr: pydicom.FileDataset
    ) -> None:
        profile = get_profile("default")
        options = ScrubOptions()
        _, manifest = scrub_dataset(synthetic_sr, profile, options)
        actions = {e.action for e in manifest.entries}
        assert "REDACT" in actions or "REPLACE_PNAME" in actions

    def test_dry_run_does_not_modify(
        self, synthetic_sr: pydicom.FileDataset
    ) -> None:
        profile = get_profile("default")
        options = ScrubOptions(dry_run=True)
        original_text_values = _get_all_text_values(synthetic_sr)
        scrubbed, _manifest = scrub_dataset(synthetic_sr, profile, options)
        scrubbed_text_values = _get_all_text_values(scrubbed)
        # In dry-run mode, values should remain unchanged
        assert original_text_values == scrubbed_text_values

    def test_original_dataset_not_mutated(
        self, synthetic_sr: pydicom.FileDataset
    ) -> None:
        profile = get_profile("default")
        options = ScrubOptions()
        original_pname = str(synthetic_sr.PatientName)
        scrub_dataset(synthetic_sr, profile, options)
        # Original dataset should be unchanged (scrubber deep-copies)
        assert str(synthetic_sr.PatientName) == original_pname


class TestScrubDatasetConservative:
    def test_all_text_is_redacted(self, synthetic_sr: pydicom.FileDataset) -> None:
        profile = get_profile("conservative")
        options = ScrubOptions()
        scrubbed, _manifest = scrub_dataset(synthetic_sr, profile, options)
        text_values = _get_all_text_values(scrubbed)
        for v in text_values:
            assert "[REDACTED:conservative_profile]" in v, (
                f"Conservative: TEXT not fully redacted: {v!r}"
            )

    def test_manifest_conservative_trigger(
        self, synthetic_sr: pydicom.FileDataset
    ) -> None:
        profile = get_profile("conservative")
        options = ScrubOptions()
        _, manifest = scrub_dataset(synthetic_sr, profile, options)
        text_entries = [e for e in manifest.entries if e.value_type == "TEXT" and e.action == "REDACT"]
        assert all(
            "conservative_profile" in e.trigger for e in text_entries
        )
