"""Scrubbing profiles for dicom-sr-scrubber.

Profiles define per-ValueType behaviour and PHI detection aggressiveness.

``default``
    Only TEXT items with detected PHI hits are redacted.
    PNAME values are always replaced.
    UIDREF values are deterministically hashed.
    DATE values are generalised to year-only.
    TIME values are zeroed.

``conservative``
    All TEXT items are redacted unconditionally.
    All PNAME values are replaced.
    All UIDREF values are hashed.
    All DATE values are generalised.
    All TIME values are zeroed.
    COMPOSITE SOPInstanceUID references are stripped.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ProfileName(str, Enum):
    DEFAULT = "default"
    CONSERVATIVE = "conservative"


@dataclass(frozen=True)
class ScrubProfile:
    """Immutable configuration for a scrub run."""

    name: ProfileName

    # TEXT handling
    redact_text_unconditionally: bool = False  # conservative=True, default=False

    # PNAME handling — always replace; no option to keep
    anonymise_pname: bool = True

    # DATE handling
    generalise_date_to_year: bool = True  # both profiles

    # TIME handling
    zero_time: bool = True  # both profiles

    # UIDREF handling
    hash_uidref: bool = True  # both profiles

    # COMPOSITE handling
    strip_composite_refs: bool = False  # conservative=True

    # Top-level DICOM tags (person names in header, not SR content tree)
    # These are always scrubbed regardless of profile.
    person_name_tags: tuple[tuple[int, int], ...] = field(
        default_factory=lambda: (
            (0x0010, 0x0010),  # PatientName
            (0x0008, 0x1048),  # Physician(s) of Record
            (0x0008, 0x1050),  # Performing Physician's Name
            (0x0008, 0x1060),  # Name of Physician(s) Reading Study
            (0x0008, 0x0090),  # Referring Physician's Name
            (0x0070, 0x0084),  # Content Creator's Name
        )
    )


_DEFAULT_PROFILE = ScrubProfile(name=ProfileName.DEFAULT)

_CONSERVATIVE_PROFILE = ScrubProfile(
    name=ProfileName.CONSERVATIVE,
    redact_text_unconditionally=True,
    strip_composite_refs=True,
)

_REGISTRY: dict[ProfileName, ScrubProfile] = {
    ProfileName.DEFAULT: _DEFAULT_PROFILE,
    ProfileName.CONSERVATIVE: _CONSERVATIVE_PROFILE,
}


def get_profile(name: str) -> ScrubProfile:
    """Return the named profile. Raises ValueError for unknown names."""
    try:
        key = ProfileName(name.lower())
    except ValueError as exc:
        valid = ", ".join(p.value for p in ProfileName)
        raise ValueError(f"Unknown profile {name!r}. Valid: {valid}") from exc
    return _REGISTRY[key]
