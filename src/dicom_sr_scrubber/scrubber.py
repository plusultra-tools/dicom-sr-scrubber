"""Main SR scrubber orchestrator.

Walk → Detect → Redact → Reassemble → Emit audit.

Public API:
    scrub_file(input_path, output_path, profile, options) -> AuditManifest
    scrub_dataset(ds, profile, options) -> (scrubbed_ds, list[AuditEntry])
"""
from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import pydicom
from pydicom.dataset import Dataset
from pydicom.uid import UID

from dicom_sr_scrubber.audit import Action, AuditEntry, AuditManifest
from dicom_sr_scrubber.citations import cite_header_tag, cite_value_type_action
from dicom_sr_scrubber.phi_detect import NerHook, detect_phi, redact_text
from dicom_sr_scrubber.profiles import ScrubProfile, get_profile
from dicom_sr_scrubber.sr_walker import (
    TAG_COMPOSITE_REF_SEQ,
    TAG_DATE_VALUE,
    TAG_PNAME_VALUE,
    TAG_TEXT_VALUE,
    TAG_TIME_VALUE,
    TAG_UID_VALUE,
    ContentItem,
    PathTuple,
    get_value_type,
    iter_content_items,
    path_to_str,
)

# Placeholder DICOM prefix for hashed UIDs (2.25 = UUID-derived UIDs per DICOM PS3.5)
_HASHED_UID_PREFIX = "2.25."

# Anonymous person name used for PNAME replacement
_ANON_PNAME = "Anonymous^Anonymous^^^"


@dataclass
class ScrubOptions:
    """Runtime options for a scrub run."""

    blacklist: frozenset[str] = field(default_factory=frozenset)
    ner_hook: NerHook | None = None
    uid_salt: str = "dicom-sr-scrubber-v1"
    dry_run: bool = False
    continue_on_error: bool = False


def _hash_uid(original_uid: str, salt: str) -> str:
    """Derive a deterministic DICOM UID from the original UID + salt."""
    digest = hashlib.sha256(f"{salt}:{original_uid}".encode()).hexdigest()
    # Convert to a numeric string; DICOM UIDs must be <= 64 chars of digits/dots
    numeric = str(int(digest[:16], 16))
    new_uid = _HASHED_UID_PREFIX + numeric
    return new_uid[:64]  # clamp to DICOM UID max length


def _hash_pname(original: str, salt: str) -> str:
    """Return a deterministic-but-anonymised PN value."""
    digest = hashlib.sha256(f"{salt}:{original}".encode()).hexdigest()[:8]
    return f"Anon{digest}^Anon{digest}^^^"


def _generalise_date(date_str: str) -> str:
    """Keep only the year part of a DICOM date string (YYYYMMDD → YYYY0101)."""
    if len(date_str) >= 4:
        return date_str[:4] + "0101"
    return "00010101"


def _scrub_content_item(
    item: ContentItem,
    path: PathTuple,
    filename: str,
    profile: ScrubProfile,
    options: ScrubOptions,
) -> list[AuditEntry]:
    """Apply per-ValueType rules to a single content item in-place.

    Returns the list of AuditEntry records produced.
    """
    entries: list[AuditEntry] = []
    vt = get_value_type(item)
    path_str = path_to_str(path)
    citations = cite_value_type_action(vt)
    citation_str = "; ".join(citations)

    def make_entry(action: Action, trigger: str, orig: str = "", scrubbed: str = "") -> AuditEntry:
        return AuditEntry(
            file=filename,
            content_item_path=path_str,
            value_type=vt,
            action=action.value,
            trigger=trigger,
            source_clause_citation=citation_str,
            original_snippet=orig[:80],
            scrubbed_snippet=scrubbed[:80],
        )

    if vt == "TEXT":
        elem = item.get(TAG_TEXT_VALUE)
        if elem is not None:
            original = str(elem.value)
            if profile.redact_text_unconditionally:
                scrubbed = "[REDACTED:conservative_profile]"
                entries.append(make_entry(Action.REDACT, "conservative_profile", original, scrubbed))
                if not options.dry_run:
                    elem.value = scrubbed
            else:
                hits = detect_phi(original, options.blacklist, options.ner_hook)
                if hits:
                    triggers = ",".join(h.pattern_name for h in hits)
                    scrubbed = redact_text(original, hits)
                    entries.append(make_entry(Action.REDACT, triggers, original, scrubbed))
                    if not options.dry_run:
                        elem.value = scrubbed
                else:
                    entries.append(make_entry(Action.KEEP, "no_phi_detected"))

    elif vt == "PNAME":
        elem = item.get(TAG_PNAME_VALUE)
        if elem is not None and profile.anonymise_pname:
            original = str(elem.value)
            scrubbed = _hash_pname(original, options.uid_salt)
            entries.append(make_entry(Action.REPLACE_PNAME, "pname_always_scrubbed", original, scrubbed))
            if not options.dry_run:
                elem.value = scrubbed
        else:
            entries.append(make_entry(Action.KEEP, "pname_keep"))

    elif vt == "DATE":
        elem = item.get(TAG_DATE_VALUE)
        if elem is not None and profile.generalise_date_to_year:
            original = str(elem.value)
            scrubbed = _generalise_date(original)
            entries.append(make_entry(Action.GENERALISE_DATE, "date_year_only", original, scrubbed))
            if not options.dry_run:
                elem.value = scrubbed
        else:
            entries.append(make_entry(Action.KEEP, "date_keep"))

    elif vt == "TIME":
        elem = item.get(TAG_TIME_VALUE)
        if elem is not None and profile.zero_time:
            original = str(elem.value)
            scrubbed = "000000.000000"
            entries.append(make_entry(Action.ZERO_TIME, "time_zero", original, scrubbed))
            if not options.dry_run:
                elem.value = scrubbed
        else:
            entries.append(make_entry(Action.KEEP, "time_keep"))

    elif vt == "UIDREF":
        elem = item.get(TAG_UID_VALUE)
        if elem is not None and profile.hash_uidref:
            original = str(elem.value)
            scrubbed = _hash_uid(original, options.uid_salt)
            entries.append(make_entry(Action.HASH_UID, "uidref_hash", original, scrubbed))
            if not options.dry_run:
                elem.value = UID(scrubbed)
        else:
            entries.append(make_entry(Action.KEEP, "uidref_keep"))

    elif vt == "COMPOSITE":
        ref_seq = item.get(TAG_COMPOSITE_REF_SEQ)
        if ref_seq is not None and profile.strip_composite_refs:
            entries.append(make_entry(Action.STRIP, "composite_strip_conservative"))
            if not options.dry_run:
                del item[TAG_COMPOSITE_REF_SEQ]
        else:
            entries.append(make_entry(Action.KEEP, "composite_keep"))

    elif vt == "CONTAINER":
        # Containers are structural; no data-level action, recurse handled by walker
        entries.append(make_entry(Action.KEEP, "container_structural"))

    else:
        # CODE, NUM, IMAGE, WAVEFORM, SCOORD, SCOORD3D, TCOORD, UNKNOWN
        entries.append(make_entry(Action.KEEP, f"{vt}_no_phi"))

    return entries


def _scrub_header_tags(
    ds: Dataset,
    profile: ScrubProfile,
    options: ScrubOptions,
    filename: str,
    manifest: AuditManifest,
) -> None:
    """Hash person-name tags in the DICOM header (not the SR content tree)."""
    for tag in profile.person_name_tags:
        elem = ds.get(tag)
        if elem is None:
            continue
        original = str(elem.value)
        if not original:
            continue
        scrubbed = _hash_pname(original, options.uid_salt)
        citation = cite_header_tag(tag)
        entry = AuditEntry(
            file=filename,
            content_item_path=f"header/({tag[0]:04X},{tag[1]:04X})",
            value_type="HEADER_PN",
            action=Action.HASH_HEADER_PN.value,
            trigger="header_person_name_tag",
            source_clause_citation=citation,
            original_snippet=original[:80],
            scrubbed_snippet=scrubbed[:80],
        )
        manifest.add(entry)
        if not options.dry_run:
            elem.value = scrubbed


def scrub_dataset(
    ds: Dataset,
    profile: ScrubProfile,
    options: ScrubOptions,
    filename: str = "<memory>",
) -> tuple[Dataset, AuditManifest]:
    """Scrub a pydicom Dataset in-place (deep copy first).

    Returns (scrubbed_ds, manifest).
    """
    scrubbed = copy.deepcopy(ds)
    manifest = AuditManifest(profile=profile.name.value)

    # Scrub header person-name tags
    _scrub_header_tags(scrubbed, profile, options, filename, manifest)

    # Walk and scrub SR content tree
    for path, item in iter_content_items(scrubbed):
        try:
            entries = _scrub_content_item(item, path, filename, profile, options)
            for e in entries:
                manifest.add(e)
        except Exception as exc:
            if options.continue_on_error:
                entry = AuditEntry(
                    file=filename,
                    content_item_path=path_to_str(path),
                    value_type="ERROR",
                    action=Action.KEEP.value,
                    trigger=f"error:{type(exc).__name__}:{exc}",
                    source_clause_citation="",
                )
                manifest.add(entry)
            else:
                raise

    return scrubbed, manifest


def scrub_file(
    input_path: Path,
    output_path: Path,
    profile: ScrubProfile,
    options: ScrubOptions,
) -> AuditManifest:
    """Load, scrub, and optionally save a DICOM SR file.

    In dry_run mode the file is not written; the manifest is still produced.
    """
    ds = pydicom.dcmread(str(input_path), force=False)
    scrubbed, manifest = scrub_dataset(ds, profile, options, filename=input_path.name)
    if not options.dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        scrubbed.save_as(str(output_path), write_like_original=False)
    return manifest


def scrub_files(
    input_paths: list[Path],
    output_dir: Path,
    profile_name: str = "default",
    dry_run: bool = False,
    continue_on_error: bool = False,
    blacklist: frozenset[str] = frozenset(),
    ner_hook: NerHook | None = None,
    uid_salt: str = "dicom-sr-scrubber-v1",
) -> AuditManifest:
    """Scrub a batch of DICOM SR files and return a combined manifest."""
    profile = get_profile(profile_name)
    options = ScrubOptions(
        blacklist=blacklist,
        ner_hook=ner_hook,
        uid_salt=uid_salt,
        dry_run=dry_run,
        continue_on_error=continue_on_error,
    )
    combined = AuditManifest(profile=profile_name)

    for input_path in input_paths:
        output_path = output_dir / input_path.name
        try:
            manifest = scrub_file(input_path, output_path, profile, options)
            combined.entries.extend(manifest.entries)
        except Exception as exc:
            if continue_on_error:
                entry = AuditEntry(
                    file=input_path.name,
                    content_item_path="file_level",
                    value_type="ERROR",
                    action=Action.KEEP.value,
                    trigger=f"file_error:{type(exc).__name__}:{exc}",
                    source_clause_citation="",
                )
                combined.add(entry)
            else:
                raise

    return combined
