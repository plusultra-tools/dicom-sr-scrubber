# Landing copy — dicom-sr-scrubber

*Carrd / micro-landing style. For the GitHub README hero and any micro-page.*

---

## Headline

**The DICOM SR PHI scrubber that dcm-anon deliberately skips.**

---

## Sub-headline

DICOM Structured Reports carry free-text findings, observer names, and acquisition dates inside a recursive content tree. Standard anonymisers miss all of it. `dicom-sr-scrubber` walks the tree, redacts the PHI, and writes a verbatim-cited audit manifest (HIPAA Safe Harbor + GDPR Art. 35 + DICOM PS3.3) — in one `pip install`.

---

## Three-point value prop

1. **Fills the documented gap.** `dcm-anon` v0.3.1 README says: *"DICOM SR content scanning — out of scope."* This is the tool that fills it.
2. **Defensible audit trail.** Every scrubbed item gets a record: tree path, ValueType, action taken, and the verbatim regulatory clause that mandates the action.
3. **One command, zero setup.** `pip install dicom-sr-scrubber && dicom-sr-scrubber --input study/ --out clean/`. Pure Python. No docker. No Java.

---

## Quick demo

```bash
pip install dicom-sr-scrubber

dicom-sr-scrubber \
  --input radiology_sr_export/ \
  --out clean_sr/ \
  --profile default \
  --dry-run   # audit only; no files written yet

# Check the audit before committing to scrub
cat clean_sr/sr_evidence.md

# Scrub for real
dicom-sr-scrubber \
  --input radiology_sr_export/ \
  --out clean_sr/
```

---

## What it scrubs

| SR Content Type | Action |
|----------------|--------|
| Free-text findings (TEXT) | Regex-redact PHI spans; preserve clinical language |
| Observer names (PNAME) | Replace with hashed anonymous name |
| Acquisition dates (DATE) | Generalise to year-only |
| Times (TIME) | Zero |
| UID references (UIDREF) | Deterministic hash (preserves referential integrity) |
| Codes, measurements | Keep unchanged |

---

## Who it's for

- **Radiology research groups** submitting SR cohorts to IRB/ethics committees.
- **Hospital IT teams** building PACS pipelines for secondary use.
- **dcm-anon users** who need the next step after top-level tag scrubbing.
- **IRB submitters** who need a per-item audit log to satisfy DPIA requirements.

---

## Pricing

CLI: **MIT, free, forever.**

Coming soon: SR scrubbing as a premium add-on inside the `dcm-anon` hosted batch pipeline (€19–29/mo).

---

## Citation (for IRB submissions)

> dicom-sr-scrubber v0.1.0 (2026). PHI scrubber for DICOM SR content trees.
> Implements HIPAA Safe Harbor (45 CFR 164.514(b)(2)) 18-identifier redaction
> and GDPR Art. 35 audit documentation for DICOM SR SOP Classes.
> https://github.com/plusultra/dicom-sr-scrubber

---

## Regulatory citations in every audit manifest

- **DICOM PS3.3 (2024c)** — ContentSequence (0040,A730), ValueType definitions
- **HIPAA Safe Harbor** — 45 CFR § 164.514(b)(2), all 18 identifier categories
- **GDPR** — Art. 4(1) (personal data), Art. 9(1) (health data), Art. 35 (DPIA)
