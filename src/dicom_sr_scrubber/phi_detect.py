"""PHI detection heuristics for DICOM SR content items.

Detection layers (applied in order, first hit wins):
1. Regex patterns — SSN, MRN-like numbers, phone, email, DOB patterns.
2. Name-blacklist matcher — simple token comparison against a configurable list.
3. NER hook — plug-in interface; no model is bundled (opt-in, see README).

All public functions are pure (no I/O). The caller decides what to do with hits.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum


class HitType(str, Enum):
    """Source category for a PHI detection hit."""

    REGEX = "regex"
    BLACKLIST = "blacklist"
    NER = "ner"


@dataclass(frozen=True)
class PhiHit:
    """A single PHI detection result."""

    hit_type: HitType
    pattern_name: str
    matched_text: str
    start: int
    end: int


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # US Social Security Number
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    # MRN-like: 5-10 digit run (conservative; may false-positive on study IDs)
    ("MRN_NUMERIC", re.compile(r"\bMRN[:\s#-]*\d{4,12}\b", re.IGNORECASE)),
    # Phone numbers (US-centric + international prefix)
    (
        "PHONE",
        re.compile(
            r"\b(?:\+?\d[\d\s\-().]{7,}\d)\b",
        ),
    ),
    # Email addresses
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
    # Dates: MM/DD/YYYY, DD-MM-YYYY, YYYY-MM-DD (free-text dates — DICOM DATE values handled separately)
    ("DATE_MDY", re.compile(r"\b\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b")),
    # NPI (US National Provider Identifier) — 10-digit with keyword
    ("NPI", re.compile(r"\bNPI[:\s]*\d{10}\b", re.IGNORECASE)),
    # Spanish DNI / NIE
    ("DNI_NIE", re.compile(r"\b[0-9]{8}[A-Za-z]\b|\b[XYZ][0-9]{7}[A-Za-z]\b")),
    # French INS / NIR
    ("NIR", re.compile(r"\b[12]\s*\d{2}\s*\d{2}\s*\d{2}\s*\d{3}\s*\d{3}\s*\d{2}\b")),
    # German Versichertennummer (10 alphanumeric starting with letter)
    ("VERSICHERTENNUMMER", re.compile(r"\b[A-Z]\d{9}\b")),
    # Accession number pattern (common hospital format)
    ("ACCESSION", re.compile(r"\bACC[:\s#-]*[A-Z0-9]{4,16}\b", re.IGNORECASE)),
]


def regex_scan(text: str) -> list[PhiHit]:
    """Return all regex-based PHI hits in ``text``."""
    hits: list[PhiHit] = []
    for name, pattern in _PATTERNS:
        for m in pattern.finditer(text):
            hits.append(
                PhiHit(
                    hit_type=HitType.REGEX,
                    pattern_name=name,
                    matched_text=m.group(),
                    start=m.start(),
                    end=m.end(),
                )
            )
    # Deduplicate overlapping matches (keep longest)
    return _deduplicate_hits(hits)


def _deduplicate_hits(hits: list[PhiHit]) -> list[PhiHit]:
    """Remove shorter overlapping hits, keeping longest span."""
    if not hits:
        return hits
    sorted_hits = sorted(hits, key=lambda h: (h.start, -(h.end - h.start)))
    result: list[PhiHit] = []
    last_end = -1
    for hit in sorted_hits:
        if hit.start >= last_end:
            result.append(hit)
            last_end = hit.end
    return result


# ---------------------------------------------------------------------------
# Name blacklist matcher
# ---------------------------------------------------------------------------

_DEFAULT_BLACKLIST: frozenset[str] = frozenset()


def blacklist_scan(
    text: str,
    blacklist: frozenset[str] = _DEFAULT_BLACKLIST,
) -> list[PhiHit]:
    """Return hits for any blacklist token found as whole words in ``text``."""
    if not blacklist:
        return []
    hits: list[PhiHit] = []
    for token in blacklist:
        if not token.strip():
            continue
        pattern = re.compile(r"\b" + re.escape(token.strip()) + r"\b", re.IGNORECASE)
        for m in pattern.finditer(text):
            hits.append(
                PhiHit(
                    hit_type=HitType.BLACKLIST,
                    pattern_name="BLACKLIST_TOKEN",
                    matched_text=m.group(),
                    start=m.start(),
                    end=m.end(),
                )
            )
    return _deduplicate_hits(hits)


# ---------------------------------------------------------------------------
# NER hook (plug-in interface, no model bundled)
# ---------------------------------------------------------------------------

# Callers can inject an NER function with this signature.
# The function must accept a string and return a list of PhiHit objects.
NerHook = Callable[[str], list[PhiHit]]


def ner_scan(text: str, ner_hook: NerHook | None = None) -> list[PhiHit]:
    """Run the optional NER hook if provided; otherwise return [].

    No NER model is bundled with dicom-sr-scrubber. To opt in, pass a
    callable that accepts a string and returns list[PhiHit].  A simple
    integration pattern::

        import medspacy

        def my_ner(text: str) -> list[PhiHit]:
            doc = nlp(text)
            return [
                PhiHit(HitType.NER, ent.label_, ent.text, ent.start_char, ent.end_char)
                for ent in doc.ents if ent.label_ in {"PERSON", "GPE", "ORG"}
            ]

        scrubber.run(ds, ner_hook=my_ner)
    """
    if ner_hook is None:
        return []
    return ner_hook(text)


# ---------------------------------------------------------------------------
# Combined detector
# ---------------------------------------------------------------------------


def detect_phi(
    text: str,
    blacklist: frozenset[str] = _DEFAULT_BLACKLIST,
    ner_hook: NerHook | None = None,
) -> list[PhiHit]:
    """Run all detection layers; return merged, deduplicated hit list."""
    hits = regex_scan(text) + blacklist_scan(text, blacklist)
    if ner_hook is not None:
        hits += ner_scan(text, ner_hook)
    return _deduplicate_hits(hits)


def redact_text(text: str, hits: list[PhiHit]) -> str:
    """Replace hit spans in ``text`` with ``[REDACTED:<pattern_name>]``.

    Spans are replaced left-to-right; overlapping spans are skipped.
    """
    if not hits:
        return text
    sorted_hits = sorted(hits, key=lambda h: h.start)
    result: list[str] = []
    cursor = 0
    for hit in sorted_hits:
        if hit.start < cursor:
            continue  # skip overlapping
        result.append(text[cursor : hit.start])
        result.append(f"[REDACTED:{hit.pattern_name}]")
        cursor = hit.end
    result.append(text[cursor:])
    return "".join(result)
