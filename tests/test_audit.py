"""Tests for audit module."""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

from dicom_sr_scrubber.audit import (
    Action,
    AuditEntry,
    AuditManifest,
    write_audit_pack,
)


class TestAuditEntry:
    def test_to_dict(self) -> None:
        entry = AuditEntry(
            file="test.dcm",
            content_item_path="root/0",
            value_type="TEXT",
            action=Action.REDACT.value,
            trigger="SSN",
            source_clause_citation="HIPAA Safe Harbor",
            original_snippet="123-45-6789",
            scrubbed_snippet="[REDACTED:SSN]",
        )
        d = entry.to_dict()
        assert d["file"] == "test.dcm"
        assert d["action"] == "REDACT"
        assert d["trigger"] == "SSN"


class TestAuditManifest:
    def test_initial_empty(self) -> None:
        m = AuditManifest()
        assert m.entries == []

    def test_add_entry(self) -> None:
        m = AuditManifest()
        e = AuditEntry(
            file="x.dcm",
            content_item_path="root/0",
            value_type="TEXT",
            action="REDACT",
            trigger="test",
            source_clause_citation="test",
        )
        m.add(e)
        assert len(m.entries) == 1

    def test_to_json_valid(self) -> None:
        m = AuditManifest(profile="default")
        e = AuditEntry(
            file="x.dcm",
            content_item_path="root/0",
            value_type="TEXT",
            action="REDACT",
            trigger="test",
            source_clause_citation="test",
        )
        m.add(e)
        j = m.to_json()
        parsed = json.loads(j)
        assert parsed["tool"] == "dicom-sr-scrubber"
        assert parsed["total_items"] == 1
        assert parsed["redacted_items"] == 1

    def test_to_markdown_contains_file(self) -> None:
        m = AuditManifest(profile="default")
        e = AuditEntry(
            file="report.dcm",
            content_item_path="root/0",
            value_type="TEXT",
            action="REDACT",
            trigger="test",
            source_clause_citation="test",
        )
        m.add(e)
        md = m.to_markdown()
        assert "report.dcm" in md
        assert "REDACT" in md

    def test_keep_action_not_counted_as_redacted(self) -> None:
        m = AuditManifest()
        for i in range(3):
            m.add(AuditEntry(
                file="x.dcm",
                content_item_path=f"root/{i}",
                value_type="CODE",
                action="KEEP",
                trigger="code_no_phi",
                source_clause_citation="",
            ))
        d = m.to_dict()
        assert d["redacted_items"] == 0


class TestWriteAuditPack:
    def test_creates_all_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir)
            m = AuditManifest(profile="default")
            m.add(AuditEntry(
                file="x.dcm",
                content_item_path="root/0",
                value_type="TEXT",
                action="REDACT",
                trigger="SSN",
                source_clause_citation="test",
                original_snippet="123",
                scrubbed_snippet="[R]",
            ))
            shas = write_audit_pack(m, [], [], out)
            assert (out / "sr_evidence.json").exists()
            assert (out / "sr_evidence.md").exists()
            assert (out / "audit.sha256").exists()
            assert "sr_evidence.json" in shas
            assert "sr_evidence.md" in shas
            assert "audit.sha256" in shas

    def test_sha256_is_correct(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir)
            m = AuditManifest(profile="conservative")
            shas = write_audit_pack(m, [], [], out)
            # Recompute the JSON sha and compare
            json_text = (out / "sr_evidence.json").read_text(encoding="utf-8")
            expected = hashlib.sha256(json_text.encode()).hexdigest()
            assert shas["sr_evidence.json"] == expected

    def test_audit_chain_includes_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir)
            m = AuditManifest()
            write_audit_pack(m, [], [], out)
            chain = (out / "audit.sha256").read_text(encoding="utf-8")
            assert "sr_evidence.json" in chain
            assert "sr_evidence.md" in chain
