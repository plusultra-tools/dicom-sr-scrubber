"""Audit manifest emitter for dicom-sr-scrubber.

Produces:
    sr_evidence.json  — machine-readable; one entry per content item touched.
    sr_evidence.md    — human-readable Markdown rendering.
    audit.sha256      — SHA-256 hash chain over inputs + outputs + manifest.

Each entry in the manifest contains:
    file             — source DICOM file path (basename)
    content_item_path — tree path string (e.g. "root/0/2/1")
    value_type       — DICOM ValueType string
    action           — KEEP | REDACT | GENERALISE_DATE | ZERO_TIME | HASH_UID | STRIP | REPLACE_PNAME
    trigger          — what caused the action (regex pattern name, profile rule, etc.)
    source_clause_citation — verbatim regulatory clause reference
    original_snippet — first 80 chars of original value (omitted if action=KEEP)
    scrubbed_snippet — first 80 chars of scrubbed value (omitted if action=KEEP)
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from dicom_sr_scrubber import __version__


class Action(str, Enum):
    KEEP = "KEEP"
    REDACT = "REDACT"
    GENERALISE_DATE = "GENERALISE_DATE"
    ZERO_TIME = "ZERO_TIME"
    HASH_UID = "HASH_UID"
    STRIP = "STRIP"
    REPLACE_PNAME = "REPLACE_PNAME"
    HASH_HEADER_PN = "HASH_HEADER_PN"


@dataclass
class AuditEntry:
    """One record in the audit manifest."""

    file: str
    content_item_path: str
    value_type: str
    action: str
    trigger: str
    source_clause_citation: str
    original_snippet: str = ""
    scrubbed_snippet: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AuditManifest:
    """Container for all audit entries from a scrub run."""

    tool: str = "dicom-sr-scrubber"
    tool_version: str = __version__
    generated_at_utc: str = field(default_factory=lambda: _isoformat_now())
    profile: str = "default"
    entries: list[AuditEntry] = field(default_factory=list)

    def add(self, entry: AuditEntry) -> None:
        self.entries.append(entry)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "tool_version": self.tool_version,
            "generated_at_utc": self.generated_at_utc,
            "profile": self.profile,
            "total_items": len(self.entries),
            "redacted_items": sum(1 for e in self.entries if e.action != Action.KEEP),
            "entries": [e.to_dict() for e in self.entries],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    def to_markdown(self) -> str:
        return _render_markdown(self)


def _isoformat_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _render_markdown(manifest: AuditManifest) -> str:
    lines: list[str] = []
    lines.append("# SR Scrubber Audit Report")
    lines.append("")
    lines.append(f"- **Tool**: {manifest.tool} v{manifest.tool_version}")
    lines.append(f"- **Generated (UTC)**: {manifest.generated_at_utc}")
    lines.append(f"- **Profile**: `{manifest.profile}`")
    lines.append(f"- **Total content items audited**: {len(manifest.entries)}")
    n_redacted = sum(1 for e in manifest.entries if e.action != Action.KEEP)
    lines.append(f"- **Items modified**: {n_redacted}")
    lines.append("")

    # Group by file
    files: dict[str, list[AuditEntry]] = {}
    for entry in manifest.entries:
        files.setdefault(entry.file, []).append(entry)

    for fname, entries in sorted(files.items()):
        lines.append(f"## `{fname}`")
        lines.append("")
        n_file_redacted = sum(1 for e in entries if e.action != Action.KEEP)
        lines.append(f"Items: {len(entries)} total, {n_file_redacted} modified")
        lines.append("")
        lines.append("| Path | ValueType | Action | Trigger | Citation |")
        lines.append("|------|-----------|--------|---------|----------|")
        for e in entries:
            citation_short = e.source_clause_citation[:60] + "…" if len(e.source_clause_citation) > 60 else e.source_clause_citation
            lines.append(
                f"| `{e.content_item_path}` | {e.value_type} | **{e.action}** | {e.trigger} | {citation_short} |"
            )
        lines.append("")

    lines.append("## Regulatory basis summary")
    lines.append("")
    lines.append("- DICOM PS3.3 (2024c) — DICOM Information Object Definitions")
    lines.append("- HIPAA Safe Harbor Method — 45 CFR § 164.514(b)(2), 18 identified categories")
    lines.append("- GDPR Art. 4(1) (personal data definition), Art. 9(1) (health data), Art. 35 (DPIA)")
    lines.append("")
    return "\n".join(lines) + "\n"


def write_audit_pack(
    manifest: AuditManifest,
    input_paths: list[Path],
    output_paths: list[Path],
    out_dir: Path,
) -> dict[str, str]:
    """Write sr_evidence.json + sr_evidence.md + audit.sha256.

    Returns a dict of {artifact_name: sha256_hex}.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    json_text = manifest.to_json()
    md_text = manifest.to_markdown()

    json_path = out_dir / "sr_evidence.json"
    md_path = out_dir / "sr_evidence.md"
    audit_path = out_dir / "audit.sha256"

    json_path.write_text(json_text, encoding="utf-8")
    md_path.write_text(md_text, encoding="utf-8")

    json_sha = _sha256_text(json_text)
    md_sha = _sha256_text(md_text)

    # Build chain: input hashes + output hashes + manifest hashes
    chain_lines: list[str] = []
    for p in sorted(input_paths):
        if p.exists():
            chain_lines.append(f"{_sha256_file(p)}  input:{p.name}")
    for p in sorted(output_paths):
        if p.exists():
            chain_lines.append(f"{_sha256_file(p)}  output:{p.name}")
    chain_lines.append(f"{json_sha}  sr_evidence.json")
    chain_lines.append(f"{md_sha}  sr_evidence.md")

    audit_text = "\n".join(chain_lines) + "\n"
    audit_path.write_text(audit_text, encoding="utf-8")

    return {
        "sr_evidence.json": json_sha,
        "sr_evidence.md": md_sha,
        "audit.sha256": _sha256_text(audit_text),
    }
