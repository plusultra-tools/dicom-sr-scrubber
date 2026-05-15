# Changelog

All notable changes to dicom-sr-scrubber are documented in this file.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning: [Semantic Versioning](https://semver.org/).

---

## [0.1.0] — 2026-05-15

### Added

- `sr_walker.py` — recursive DICOM SR ContentSequence (0040,A730) walker;
  yields `(path, ContentItem)` tuples for every node in the tree.
- `phi_detect.py` — PHI detection heuristics: regex (SSN, MRN, phone, email,
  DOB, NPI, DNI/NIE, NIR, Versichertennummer, accession), name-blacklist
  matcher, and an optional NER plug-in interface (no model bundled).
- `scrubber.py` — main orchestrator: walk → detect → redact → reassemble;
  header person-name tags hashed; per-ValueType rules applied.
- `profiles.py` — `default` and `conservative` scrubbing profiles.
- `citations.py` + `data/citations.yaml` — verbatim regulatory citations
  (DICOM PS3.3, HIPAA Safe Harbor 45 CFR 164.514(b)(2), GDPR Art. 4/9/35).
- `audit.py` — SHA-256 chain over inputs + outputs + manifest;
  emits `sr_evidence.json`, `sr_evidence.md`, `audit.sha256`.
- `cli.py` — `dicom-sr-scrubber` CLI with `--input`, `--out`, `--profile`,
  `--dry-run`, `--continue-on-error`, `--uid-salt`, `--blacklist`.
- Full pytest test suite with synthetic in-memory SR fixtures (no real PHI).
- `docs/sr-citation-map.md` — table mapping redaction triggers to source clauses.
- `examples/quickstart/` — synthetic SR generator and README.

### Per-ValueType rules (v0.1)

| ValueType | Default action | Conservative action |
|-----------|---------------|---------------------|
| TEXT | Redact PHI-matching spans only | Redact ALL unconditionally |
| PNAME | Replace with hashed anon name | Replace with hashed anon name |
| DATE | Generalise to year-only (YYYY0101) | Same |
| TIME | Zero (000000.000000) | Same |
| UIDREF | Hash-derive new UID | Same |
| COMPOSITE | Keep (SOPInstanceUID preserved) | Strip reference |
| CODE, NUM | Keep | Keep |
| CONTAINER | Recurse | Recurse |
| IMAGE, WAVEFORM, SCOORD, TCOORD | Keep | Keep |

### Known limitations / out of scope for v0.1

- Enhanced SR multi-frame complexities (ACQUISITION CONTEXT, WAVEFORM sequences
  with embedded annotation text) are not fully handled; coordinates kept, text
  overlays within IMAGE/WAVEFORM items not scanned.
- No LLM-backed free-text NER; NER is a plug-in interface only.
- UID remapping map is per-run only; not persisted between runs unless you
  implement your own session state.
- Non-English PHI patterns (beyond DNI/NIE/NIR/Versichertennummer): partial;
  contributions welcome.
