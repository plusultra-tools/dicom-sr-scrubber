# dicom-sr-scrubber

**Parses and scrubs PHI from DICOM Structured Report (SR) content trees.** The piece `dcm-anon` deliberately does not ship — single `pip install`, single command, recursive walk over the SR `ContentSequence`, audit log of every item touched.

```bash
pip install dicom-sr-scrubber
dicom-sr-scrub input.dcm output.dcm
```

Pairs with [dcm-anon](https://github.com/plusultra/dicom-anon-api) — the recommended pipeline is:

```bash
dcm-anon scrub raw.dcm clean.dcm        # top-level tags + nested sequences
dicom-sr-scrub clean.dcm final.dcm      # SR content tree
```

---

## Why this exists

`dcm-anon` ships PHI scrubbing for top-level DICOM tags and nested
sequences (PatientName, PatientID, AccessionNumber, the standard PS3.15
Basic De-identification Profile set). Its `README.md` documents the
explicit limitation:

> **DICOM SR / Structured Report content scanning.** Free-text inside SR
> sequences may contain PHI; we do not parse SR semantics.

That gap is real. DICOM Structured Reports (SOP Classes `Basic Text SR`,
`Enhanced SR`, `Comprehensive SR`, `Mammography CAD SR`,
`Radiation Dose SR`, etc.) carry their payload as a **recursive tree of
content items** under `ContentSequence (0040,A730)`. Each content item
has a `ValueType (0040,A040)` (TEXT, NUM, CODE, PNAME, DATE, TIME,
UIDREF, COMPOSITE, IMAGE, WAVEFORM, CONTAINER, SCOORD, TCOORD), a
`RelationshipType (0040,A010)` (CONTAINS, HAS PROPERTIES, HAS OBS
CONTEXT, …), and either a value or another `ContentSequence`. PHI lives
*inside* this tree: free-text findings, observer names (`PNAME`),
acquisition dates (`DATE`), patient identifiers as text (`TEXT`).

A naive `dcm-anon`-style top-level tag scrub leaves all of that intact.

No widely-used OSS DICOM tool walks the SR content tree for PHI today.
`dcmtk`'s `dsr2html` parses but does not scrub. `pydicom` exposes the
tree but ships no PHI-aware walker. `gdcm`'s anonymizer skips SR
semantics. CTP (Clinical Trial Processor) can be scripted but requires
hand-written profiles per institution.

`dicom-sr-scrubber` is the missing walker.

## What it does

1. `pip install dicom-sr-scrubber` — pure Python, single dependency
   (`pydicom>=2.4`).
2. `dicom-sr-scrub scrub input.dcm output.dcm` — recursively walks
   `ContentSequence`, applies per-`ValueType` PHI rules, writes a new
   DICOM file with the SR content tree cleaned, leaves all non-SR
   pixel/metadata untouched.
3. `dicom-sr-scrub verify output.dcm` — re-parses the scrubbed file and
   reports whether any PHI pattern survived in the SR content tree.
   Exit `0` = clean, exit `1` = residual PHI.
4. Every scrub run emits an **audit log** (JSON) listing every content
   item visited, its tree path, its `ValueType`, the rule that fired
   (or `PASS`), and the action taken (`REDACT`, `GENERALIZE_DATE_YEAR`,
   `STRIP`, `KEEP`). CI-friendly: pipe to `jq`, fail builds on
   surprises.

## Per-ValueType rules (v0.1)

| ValueType | Default rule | Rationale |
|---|---|---|
| `TEXT` | Pattern-match for PHI tokens (names, MRNs, free-form dates, phone, email). Redact span; replace with `[REDACTED]`. | Free-text is the highest-risk surface in SR. |
| `PNAME` | Always replace with `Anonymous^Anonymous^^^`. | A `PNAME` *is* a person name by definition. |
| `DATE` | Generalize to year-only (`YYYY0101`). Configurable: `--date-policy={year,strip,keep}`. | HIPAA Safe Harbor permits year for non-elderly subjects; year-only is the common research-grade choice. |
| `TIME` | Strip (`000000.000000`). | Time-of-day is rarely scientifically necessary; high re-identification risk when combined with date. |
| `CODE` | Keep (coded values are dictionary entries, not PHI). | SNOMED CT / LOINC / RadLex codes are public. |
| `NUM` | Keep (measurement values are not PHI). | Body temperature `37.0` is not identifying. |
| `UIDREF` | Replace with deterministic hash-derived UID (same input → same output across runs in the same session). | Preserves referential integrity inside the report; breaks linkability to the source archive. |
| `COMPOSITE` | Strip the SOPInstanceUID reference (set to placeholder UID). | A reference to the source image series can leak the patient through the receiving PACS. |
| `IMAGE` / `WAVEFORM` / `SCOORD` / `TCOORD` | Keep coordinate / reference fields, strip embedded annotation text if any. | Geometry is not PHI; text overlays may be. |
| `CONTAINER` | Recurse into child `ContentSequence`. | Containers are structural, not data. |

Rules are pluggable — drop a Python module implementing the
`PhiRule` protocol in `~/.config/dicom-sr-scrubber/rules.d/` and it is
loaded at startup.

## What it does NOT do

- **Not a replacement for `dcm-anon`.** It only touches the SR content
  tree. Run `dcm-anon` first to scrub top-level tags and nested
  non-SR sequences.
- **No semantic understanding of the report.** It does not "read the
  finding"; it pattern-matches PHI tokens. False negatives are
  possible on adversarial free-text (e.g., a name spelled
  phonetically). The audit log makes residual review tractable.
- **No DICOM network transport.** This is a file-in, file-out CLI. Pair
  with `dcmtk`'s `storescu` / `storescp` for transport.
- **No re-identification.** UID remapping is per-session only; the map
  is not persisted unless you pass `--uid-map-out path.json`.

## Differentiation

| Tool | SR content-tree walker | PHI-aware | OSS | Bundled rules |
|---|---|---|---|---|
| `dcm-anon` | no (documented gap) | yes | yes | yes |
| `dcmtk` `dsr2html` | yes | no (read-only) | yes | n/a |
| `dcmtk` `dcmodify` | no | partial | yes | manual |
| `pydicom` | tree access only | no | yes | n/a |
| `gdcm` anonymizer | no | partial | yes | basic |
| CTP (RSNA) | scriptable | yes | yes | per-institution scripts |
| **dicom-sr-scrubber** | **yes** | **yes** | **yes** | **yes (per-ValueType)** |

## Pricing

- **CLI: MIT, free, forever.**
- **Hosted add-on on the `dcm-anon` Phase 2 plan** — €19–29/mo,
  bundles SR scrubbing into the same hosted batch pipeline (drop a
  DICOM folder, get a scrubbed folder plus audit log back). Stripe
  billing once the demand signal justifies it.

## Roadmap

- **v0.1 (this release)** — Walker, per-`ValueType` rules, CLI,
  audit log, `verify` subcommand, synthetic fixture tests.
- **v0.2** — Configurable rule plug-ins, structured-error JSON
  identical to `dcm-anon`'s.
- **v0.3** — Optional LLM-backed free-text PHI detection for `TEXT`
  items (opt-in, local model only, no cloud).
- **v1.0** — Stable rule-protocol API; semver guarantees.

## Audience

- Radiology research groups submitting de-identified SR cohorts to
  IRB / ethics committees.
- Hospital IT departments running PACS pipelines that need defensible
  SR-level scrubbing for secondary use.
- IRB / ethics submitters needing an audit log per study.
- Distribution: `r/medicalimaging`, `r/healthIT`, dev.to,
  `awesome-dicom` lists, the `dcm-anon` user channel (cross-promo).

## Install

```bash
pip install dicom-sr-scrubber        # PyPI (once published)
# or from source:
pip install git+https://github.com/plusultra/dicom-sr-scrubber.git
```

**Requirements**: Python 3.10+, `pydicom>=2.4`, `pyyaml>=6.0`, `pydantic>=2.0`.

## Quickstart

```bash
# Default profile: redact only TEXT items that match PHI patterns
dicom-sr-scrubber --input study_sr/ --out clean_sr/

# Conservative: redact ALL text items unconditionally + strip COMPOSITE refs
dicom-sr-scrubber --input study_sr/ --out clean_sr/ --profile conservative

# Dry-run: emit audit only, no DICOM files written
dicom-sr-scrubber --input study_sr/ --out audit_only/ --dry-run

# Add institution-specific name tokens to the blacklist
dicom-sr-scrubber --input study_sr/ --out clean_sr/ \
  --blacklist "DrSmith,JohnDoe,ClinicA"
```

## CLI reference

```
dicom-sr-scrubber [options]

  --input PATH[,PATH...]   DICOM SR file(s) or directory (recursive .dcm scan)
  --out DIR                Output directory for scrubbed files + manifests
  --profile {default,conservative}
                           Scrubbing aggressiveness (default: default)
  --dry-run                Emit audit only; do not write scrubbed files
  --continue-on-error      Log per-file errors; do not abort the batch
  --uid-salt STRING        Per-project UID/PNAME hash salt (default: "dicom-sr-scrubber-v1")
  --blacklist TOKEN,...    Additional name tokens to treat as PHI in TEXT fields
  --version                Show version and exit
```

## Output files

After each run, `--out` contains:

| File | Description |
|------|-------------|
| `*.dcm` | Scrubbed DICOM SR objects (unless `--dry-run`) |
| `sr_evidence.json` | Machine-readable audit manifest (one entry per content item) |
| `sr_evidence.md` | Human-readable rendering for IRB / DPIA documentation |
| `audit.sha256` | SHA-256 chain over inputs + outputs + manifest |

### `sr_evidence.json` format (excerpt)

```json
{
  "tool": "dicom-sr-scrubber",
  "tool_version": "0.1.0",
  "profile": "default",
  "total_items": 42,
  "redacted_items": 7,
  "entries": [
    {
      "file": "study_sr.dcm",
      "content_item_path": "root/0",
      "value_type": "TEXT",
      "action": "REDACT",
      "trigger": "SSN,EMAIL",
      "source_clause_citation": "DICOM PS3.3 C.17.3.3.5; HIPAA Safe Harbor identifiers 1,3-8 (45 CFR 164.514(b)(2)); GDPR Art. 4(1)",
      "original_snippet": "Patient John Doe (SSN: 123-45-6789)...",
      "scrubbed_snippet": "Patient John Doe ([REDACTED:SSN])..."
    }
  ]
}
```

## Citation for IRB / DPIA submissions

```
dicom-sr-scrubber v0.1.0 (2026). PHI scrubber for DICOM Structured Report
content trees. Implements HIPAA Safe Harbor (45 CFR 164.514(b)(2)) 18-identifier
redaction and GDPR Art. 35 audit documentation for DICOM SR SOP Classes.
https://github.com/plusultra/dicom-sr-scrubber
```

## Regulatory citation coverage

| Regulation | Coverage |
|-----------|---------|
| DICOM PS3.3 (2024c) | Per-tag and per-ValueType citations (ContentSequence, TextValue, PersonName, Date, Time, UID, Composite) |
| HIPAA Safe Harbor (45 CFR 164.514(b)(2)) | All 18 identifiers verbatim |
| GDPR | Art. 4(1), Art. 9(1), Art. 35, Recital 26 |

Full citation map: [`docs/sr-citation-map.md`](docs/sr-citation-map.md).

## Known gaps and out-of-scope items (honest)

- **Enhanced SR multi-frame**: ACQUISITION CONTEXT sequences and WAVEFORM items
  with embedded annotation text are not scanned for PHI content in v0.1.
  Geometry coordinates are preserved; text overlays in IMAGE/WAVEFORM items
  are not inspected.
- **NER not bundled**: The NER detection layer is a plug-in interface only.
  No NLP model ships with this package (opt-in; see `phi_detect.py`
  `NerHook` type for the integration contract).
- **UID session scope**: UID remapping is per-run; the map is not persisted
  between runs unless the caller manages `--uid-salt` consistency.
- **Not a complete anonymiser**: must be combined with a top-level tag scrubber
  (e.g. `dcm-anon`) for full DICOM anonymisation.
- **Age-check for >89 rule**: HIPAA Safe Harbor requires year suppression for
  subjects aged >89; this tool generalises all dates to year-only but does not
  implement the age-computation check.

## Contributing

Open an issue with a real SR (anonymised already, please) that the
scrubber missed PHI in, or that it over-redacted. PRs welcome —
especially for additional `ValueType` rules and locale-specific PHI
patterns (Spanish DNI, French INS, German Versichertennummer).

## License

MIT. See [LICENSE](LICENSE).
