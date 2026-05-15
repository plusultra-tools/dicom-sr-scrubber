# Quickstart example

This directory contains a standalone script to generate a synthetic DICOM SR
file with deliberate (fake) PHI patterns, so you can test `dicom-sr-scrubber`
without needing real patient data.

## Usage

```bash
# From the repo root
cd examples/quickstart

# Generate the synthetic SR
python generate_synthetic_sr.py --out-dir ./output

# Dry-run: emit audit manifest, do not write scrubbed files
dicom-sr-scrubber --input ./output/synthetic_sr.dcm --out ./scrubbed/ --dry-run

# Inspect the audit manifest
cat ./scrubbed/sr_evidence.md

# Full scrub: write cleaned SR + manifest
dicom-sr-scrubber --input ./output/synthetic_sr.dcm --out ./scrubbed/

# Conservative mode: redact ALL text unconditionally
dicom-sr-scrubber \
  --input ./output/synthetic_sr.dcm \
  --out ./scrubbed_conservative/ \
  --profile conservative
```

## What is in the synthetic SR

The generated SR (`synthetic_sr.dcm`) contains:

| Content type | Synthetic value | PHI? |
|-------------|----------------|------|
| TEXT item 1 | Fake SSN, MRN, email, phone embedded in clinical text | Yes |
| TEXT item 2 | Clean clinical text (no PHI) | No |
| PNAME item | `Radiologist^James^^^` | Yes |
| DATE item | `20260515` | Yes (full date) |
| CODE item | SNOMED code for liver | No |

After scrubbing:
- TEXT item 1: SSN, MRN, email, phone spans replaced with `[REDACTED:SSN]` etc.
- TEXT item 2: unchanged (no PHI detected)
- PNAME: replaced with hashed anonymous name
- DATE: generalised to `20260101` (year-only)
- CODE: unchanged

The audit manifest (`sr_evidence.json`) lists every item visited with
its action and regulatory citation.
