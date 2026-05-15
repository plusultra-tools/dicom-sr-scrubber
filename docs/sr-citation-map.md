# SR Citation Map

Maps each redaction trigger to its primary regulatory source clause.

| Trigger | ValueType | Action | Primary clause |
|---------|-----------|--------|----------------|
| `SSN` | TEXT | REDACT | HIPAA Safe Harbor identifier 7 (Social security numbers); 45 CFR 164.514(b)(2) |
| `MRN_NUMERIC` | TEXT | REDACT | HIPAA Safe Harbor identifier 8 (Medical record numbers); 45 CFR 164.514(b)(2) |
| `PHONE` | TEXT | REDACT | HIPAA Safe Harbor identifier 4 (Telephone numbers) + 5 (Fax numbers); 45 CFR 164.514(b)(2) |
| `EMAIL` | TEXT | REDACT | HIPAA Safe Harbor identifier 6 (Electronic mail addresses); 45 CFR 164.514(b)(2) |
| `DATE_MDY` | TEXT | REDACT | HIPAA Safe Harbor identifier 3 (Dates); 45 CFR 164.514(b)(2) |
| `NPI` | TEXT | REDACT | HIPAA Safe Harbor identifier 11 (Certificate/license numbers); 45 CFR 164.514(b)(2) |
| `DNI_NIE` | TEXT | REDACT | GDPR Art. 4(1) — national identification number is a personal data identifier |
| `NIR` | TEXT | REDACT | GDPR Art. 4(1) — French health system identifier (NIR/INS) |
| `VERSICHERTENNUMMER` | TEXT | REDACT | GDPR Art. 4(1) — German statutory health insurance number |
| `ACCESSION` | TEXT | REDACT | HIPAA Safe Harbor identifier 18 (unique identifying number/code); 45 CFR 164.514(b)(2) |
| `BLACKLIST_TOKEN` | TEXT | REDACT | Caller-supplied name token; HIPAA Safe Harbor identifier 1 (Names) |
| `conservative_profile` | TEXT | REDACT | Profile-level unconditional redaction; DICOM PS3.3 C.17.3.3.5 TextValue |
| `pname_always_scrubbed` | PNAME | REPLACE_PNAME | DICOM PS3.3 C.17.3.3.8 (PNAME = Person Name by definition); HIPAA Safe Harbor identifier 1 (Names); GDPR Art. 4(1), Art. 9(1) |
| `date_year_only` | DATE | GENERALISE_DATE | HIPAA Safe Harbor identifier 3 (Dates, except year); 45 CFR 164.514(b)(2); DICOM PS3.3 C.17.3.3.3 |
| `time_zero` | TIME | ZERO_TIME | HIPAA Safe Harbor identifier 3 (Dates/Times); DICOM PS3.3 C.17.3.3.4 |
| `uidref_hash` | UIDREF | HASH_UID | HIPAA Safe Harbor identifier 18 (unique identifiers); DICOM PS3.3 C.17.3.3.9 |
| `composite_strip_conservative` | COMPOSITE | STRIP | HIPAA Safe Harbor identifier 13 (device identifiers); DICOM PS3.3 C.17.3.3.11 |
| `header_person_name_tag` | HEADER_PN | HASH_HEADER_PN | HIPAA Safe Harbor identifier 1 (Names); DICOM PS3.3 per-tag (PatientName C.7.1.1, Physician fields C.7.3.1) |

## Notes

1. **KEEP actions** are not listed here; they require no regulatory justification (no PHI affected).
2. **Conservative profile** treats all TEXT items as containing PHI unconditionally. The trigger `conservative_profile` maps to DICOM PS3.3 C.17.3.3.5 as the definition of the risk surface, not a specific detection.
3. **UIDREF hashing** preserves referential integrity within the SR document while preventing linkage to the source PACS archive. This satisfies GDPR Recital 26 (information no longer attributable to a data subject without disproportionate effort) for the UID dimension only.
4. **DATE generalisation** to year-only follows the HIPAA Safe Harbor safe harbour for research cohorts. For subjects aged >89, the Safe Harbor requires year to be suppressed or bucketed into "90+"; this tool does not implement age-check logic (would require PatientBirthDate + StudyDate); callers must handle this separately.
5. **Enhanced SR multi-frame complexities** — ACQUISITION CONTEXT sequences and WAVEFORM sequences with embedded annotation text are not fully scanned for PHI in v0.1. See CHANGELOG Known Limitations.
