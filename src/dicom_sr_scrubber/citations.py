"""Citation loader for dicom-sr-scrubber.

Loads verbatim regulatory citations from data/citations.yaml and provides
helper functions to look up the relevant clause for a given action or tag.

The citations.yaml file ships with the package and is loaded lazily.
"""
from __future__ import annotations

import importlib.resources
from functools import lru_cache
from typing import Any

import yaml


@lru_cache(maxsize=1)
def _load_citations() -> dict[str, Any]:
    """Load and cache the citations YAML bundled with the package.

    Resolution order:
    1. Relative to this source file (src/dicom_sr_scrubber/ → data/citations.yaml)
       — covers editable installs and the normal package layout.
    2. importlib.resources (for installed wheel with package_data).
    """
    import pathlib

    # Primary: relative to this file (works for editable installs)
    # __file__ = <project>/src/dicom_sr_scrubber/citations.py
    # .parent      => src/dicom_sr_scrubber/
    # .parent.parent => src/
    # .parent.parent.parent => <project root>  (dicom-sr-scrubber/)
    here = pathlib.Path(__file__).parent  # src/dicom_sr_scrubber/
    candidate = here.parent.parent / "data" / "citations.yaml"
    if candidate.exists():
        return yaml.safe_load(candidate.read_text(encoding="utf-8"))  # type: ignore[no-any-return]

    # Secondary: importlib.resources (installed wheel)
    try:
        pkg_data = importlib.resources.files("dicom_sr_scrubber").joinpath(
            "data/citations.yaml"
        )
        text = pkg_data.read_text(encoding="utf-8")
        return yaml.safe_load(text)  # type: ignore[no-any-return]
    except (FileNotFoundError, TypeError):
        pass

    raise FileNotFoundError(
        f"citations.yaml not found. Tried: {candidate}. "
        "Re-install the package or ensure data/citations.yaml is present."
    )


def hipaa_identifiers() -> list[dict[str, Any]]:
    """Return the 18 HIPAA Safe Harbor identifiers (45 CFR 164.514(b)(2))."""
    data = _load_citations()
    return data["hipaa_safe_harbor"]["verbatim_identifiers"]  # type: ignore[no-any-return]


def dicom_tag_citation(tag_str: str) -> dict[str, Any] | None:
    """Return the DICOM PS3.3 citation entry for a tag like '(0040,A040)'.

    Returns None if the tag is not in the citation map.
    """
    data = _load_citations()
    entries: list[dict[str, Any]] = data["dicom_ps3_3"]["entries"]
    tag_normalised = tag_str.upper().replace(" ", "")
    for entry in entries:
        if entry["tag"].upper().replace(" ", "") == tag_normalised:
            return entry
    return None


def gdpr_article(article_ref: str) -> dict[str, Any] | None:
    """Return the GDPR entry for a reference like 'Art. 35'."""
    data = _load_citations()
    for entry in data["gdpr"]["entries"]:
        if entry["article"].strip() == article_ref.strip():
            return entry  # type: ignore[no-any-return]
    return None


def cite_value_type_action(value_type: str) -> list[str]:
    """Return a list of regulatory clause strings relevant to a ValueType action.

    Used in the audit manifest to populate the ``source_clause_citation`` field.
    """
    vt = value_type.upper()
    clauses: list[str] = []
    if vt == "TEXT":
        clauses.append("DICOM PS3.3 C.17.3.3.5 (TextValue); HIPAA Safe Harbor identifiers 1,3-8 (45 CFR 164.514(b)(2)); GDPR Art. 4(1)")
    elif vt == "PNAME":
        clauses.append("DICOM PS3.3 C.17.3.3.8 (PersonName); HIPAA Safe Harbor identifier 1 (Names); GDPR Art. 4(1), Art. 9(1)")
    elif vt == "DATE":
        clauses.append("DICOM PS3.3 C.17.3.3.3 (Date); HIPAA Safe Harbor identifier 3 (Dates, 45 CFR 164.514(b)(2))")
    elif vt == "TIME":
        clauses.append("DICOM PS3.3 C.17.3.3.4 (Time); HIPAA Safe Harbor identifier 3 (Dates/Times)")
    elif vt == "UIDREF":
        clauses.append("DICOM PS3.3 C.17.3.3.9 (UID); HIPAA Safe Harbor identifier 18 (unique identifiers)")
    elif vt == "COMPOSITE":
        clauses.append("DICOM PS3.3 C.17.3.3.11 (COMPOSITE); HIPAA Safe Harbor identifier 13 (device identifiers)")
    else:
        clauses.append("DICOM PS3.3 C.17.3.1 (SR Document Content Module)")
    return clauses


def cite_header_tag(tag: tuple[int, int]) -> str:
    """Return a short citation string for a top-level PHI tag."""
    tag_str = f"({tag[0]:04X},{tag[1]:04X})"
    entry = dicom_tag_citation(tag_str)
    if entry:
        return f"DICOM PS3.3 {entry['section']}; HIPAA Safe Harbor identifier 1 (Names)"
    return f"DICOM PS3.3 tag {tag_str}; HIPAA Safe Harbor identifier 1 (Names)"
