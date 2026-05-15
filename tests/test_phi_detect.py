"""Tests for phi_detect module."""
from __future__ import annotations

from dicom_sr_scrubber.phi_detect import (
    HitType,
    PhiHit,
    blacklist_scan,
    detect_phi,
    ner_scan,
    redact_text,
    regex_scan,
)


class TestRegexScan:
    def test_detects_ssn(self) -> None:
        hits = regex_scan("SSN is 123-45-6789 here")
        assert any(h.pattern_name == "SSN" for h in hits)

    def test_detects_mrn(self) -> None:
        hits = regex_scan("MRN: 1234567 is the record")
        assert any(h.pattern_name == "MRN_NUMERIC" for h in hits)

    def test_detects_email(self) -> None:
        hits = regex_scan("Contact: john.doe@hospital.org")
        assert any(h.pattern_name == "EMAIL" for h in hits)

    def test_detects_phone(self) -> None:
        hits = regex_scan("+1-555-123-4567")
        assert any(h.pattern_name == "PHONE" for h in hits)

    def test_detects_date_mdy(self) -> None:
        hits = regex_scan("DOB: 01/23/1985")
        assert any(h.pattern_name == "DATE_MDY" for h in hits)

    def test_clean_text_no_hits(self) -> None:
        hits = regex_scan("No abnormalities detected in the right lung base.")
        assert hits == []

    def test_returns_hit_type_regex(self) -> None:
        hits = regex_scan("123-45-6789")
        assert all(h.hit_type == HitType.REGEX for h in hits)

    def test_no_overlap_in_results(self) -> None:
        hits = regex_scan("SSN 123-45-6789 and email test@x.com")
        for i, h1 in enumerate(hits):
            for j, h2 in enumerate(hits):
                if i != j:
                    assert h1.end <= h2.start or h2.end <= h1.start, (
                        f"Overlapping hits: {h1} and {h2}"
                    )

    def test_detects_accession(self) -> None:
        hits = regex_scan("ACC: ABCD1234 was the accession")
        assert any(h.pattern_name == "ACCESSION" for h in hits)

    def test_detects_npi(self) -> None:
        hits = regex_scan("NPI: 1234567890")
        assert any(h.pattern_name == "NPI" for h in hits)


class TestBlacklistScan:
    def test_hits_blacklist_token(self) -> None:
        bl = frozenset(["JohnDoe"])
        hits = blacklist_scan("Patient JohnDoe presented today", bl)
        assert len(hits) == 1
        assert hits[0].hit_type == HitType.BLACKLIST

    def test_case_insensitive(self) -> None:
        bl = frozenset(["johndoe"])
        hits = blacklist_scan("Patient JOHNDOE presented", bl)
        assert len(hits) == 1

    def test_empty_blacklist_no_hits(self) -> None:
        hits = blacklist_scan("any text here", frozenset())
        assert hits == []

    def test_whole_word_only(self) -> None:
        bl = frozenset(["John"])
        # "Johnson" should not match "John" as a whole word
        hits = blacklist_scan("Johnson is not John", bl)
        assert len(hits) == 1
        assert hits[0].matched_text.lower() == "john"


class TestNerScan:
    def test_no_hook_returns_empty(self) -> None:
        assert ner_scan("some text", None) == []

    def test_custom_hook_called(self) -> None:
        fake_hit = PhiHit(HitType.NER, "PERSON", "Alice", 0, 5)

        def fake_ner(text: str) -> list[PhiHit]:
            return [fake_hit] if "Alice" in text else []

        hits = ner_scan("Alice was here", fake_ner)
        assert len(hits) == 1
        assert hits[0].hit_type == HitType.NER


class TestDetectPhi:
    def test_combined_detection(self) -> None:
        hits = detect_phi("SSN 123-45-6789 email test@x.com")
        pattern_names = {h.pattern_name for h in hits}
        assert "SSN" in pattern_names
        assert "EMAIL" in pattern_names

    def test_blacklist_combined(self) -> None:
        bl = frozenset(["DrSmith"])
        hits = detect_phi("Reported by DrSmith, SSN 123-45-6789", blacklist=bl)
        assert any(h.hit_type == HitType.BLACKLIST for h in hits)
        assert any(h.hit_type == HitType.REGEX for h in hits)


class TestRedactText:
    def test_redacts_ssn(self) -> None:
        hits = regex_scan("SSN: 123-45-6789")
        result = redact_text("SSN: 123-45-6789", hits)
        assert "123-45-6789" not in result
        assert "[REDACTED:" in result

    def test_preserves_non_phi(self) -> None:
        hits = regex_scan("call 555-867-5309 and come back")
        result = redact_text("call 555-867-5309 and come back", hits)
        assert "call" in result
        assert "and come back" in result

    def test_no_hits_unchanged(self) -> None:
        text = "Nothing PHI here."
        result = redact_text(text, [])
        assert result == text

    def test_multiple_redactions(self) -> None:
        text = "SSN: 123-45-6789 email test@ex.com"
        hits = detect_phi(text)
        result = redact_text(text, hits)
        assert "123-45-6789" not in result
        assert "test@ex.com" not in result
        assert result.count("[REDACTED:") == len(hits)
