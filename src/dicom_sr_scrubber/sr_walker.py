"""DICOM SR content-tree walker.

Walks the ContentSequence (0040,A730) recursively, yielding
(path, content_item) tuples for every node in the tree.

DICOM SR ValueType vocabulary (PS3.3 Table C.17.3-8):
    TEXT, PNAME, DATE, TIME, CODE, NUM, UIDREF, COMPOSITE,
    IMAGE, WAVEFORM, SCOORD, SCOORD3D, TCOORD, CONTAINER.

Each yielded ``path`` is a tuple of integer indices representing
the depth-first position of the item in the tree, e.g. (0, 2, 1).
The root item (if present as the top-level dataset) is at path ().
"""
from __future__ import annotations

from collections.abc import Generator

import pydicom
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence

# DICOM tag constants
TAG_CONTENT_SEQUENCE = (0x0040, 0xA730)
TAG_VALUE_TYPE = (0x0040, 0xA040)
TAG_RELATIONSHIP_TYPE = (0x0040, 0xA010)
TAG_CONCEPT_NAME_CODE_SEQ = (0x0040, 0xA043)
TAG_TEXT_VALUE = (0x0040, 0xA160)
TAG_PNAME_VALUE = (0x0040, 0xA123)
TAG_DATE_VALUE = (0x0040, 0xA121)
TAG_TIME_VALUE = (0x0040, 0xA122)
TAG_UID_VALUE = (0x0040, 0xA124)
TAG_NUMERIC_VALUE = (0x0040, 0xA300)
TAG_COMPOSITE_REF_SEQ = (0x0040, 0xA504)
TAG_IMAGE_REF_SEQ = (0x0008, 0x1140)
TAG_WAVEFORM_REF_SEQ = (0x0040, 0xA9C1)
TAG_SCOORD_DATA = (0x0070, 0x0022)
TAG_TCOORD_DATA = (0x0040, 0xA130)
TAG_CONCEPT_CODE_SEQ = (0x0040, 0xA168)

# Leaf ValueTypes that do NOT have child ContentSequence
LEAF_VALUE_TYPES = frozenset(
    {
        "TEXT",
        "PNAME",
        "DATE",
        "TIME",
        "CODE",
        "NUM",
        "UIDREF",
        "COMPOSITE",
        "IMAGE",
        "WAVEFORM",
        "SCOORD",
        "SCOORD3D",
        "TCOORD",
    }
)

ContentItem = Dataset
PathTuple = tuple[int, ...]


def iter_content_items(
    ds: Dataset,
    _path: PathTuple = (),
) -> Generator[tuple[PathTuple, ContentItem], None, None]:
    """Recursively yield (path, content_item) for every item in the SR tree.

    Parameters
    ----------
    ds:
        A pydicom Dataset that is either the root SR SOP instance or a
        single ContentSequence item (ContentItem).
    _path:
        Internal accumulator — callers should leave this at the default.

    Yields
    ------
    (path, item) where ``path`` is a tuple of integer indices and
    ``item`` is the pydicom Dataset for that content item.
    """
    # Attempt to enter the top-level ContentSequence if ds is the root SOP
    content_seq: Sequence | None = _get_sequence(ds, TAG_CONTENT_SEQUENCE)
    if content_seq is None:
        # ds *is* the content item itself
        yield _path, ds
        child_seq = _get_sequence(ds, TAG_CONTENT_SEQUENCE)
        if child_seq is not None:
            for i, child in enumerate(child_seq):
                yield from iter_content_items(child, (*_path, i))
        return

    # ds is the root SOP — iterate its ContentSequence
    for i, item in enumerate(content_seq):
        yield from iter_content_items(item, (*_path, i))


def _get_sequence(ds: Dataset, tag: tuple[int, int]) -> Sequence | None:
    """Return the pydicom Sequence at ``tag`` or None if absent / empty."""
    elem = ds.get(tag)
    if elem is None:
        return None
    val = elem.value
    if not isinstance(val, Sequence):
        return None
    if len(val) == 0:
        return None
    return val


def get_value_type(item: ContentItem) -> str:
    """Return the ValueType string for a content item, or 'UNKNOWN'."""
    elem = item.get(TAG_VALUE_TYPE)
    if elem is None:
        return "UNKNOWN"
    return str(elem.value).strip().upper()


def path_to_str(path: PathTuple) -> str:
    """Convert a path tuple to a human-readable string like 'root/0/2/1'."""
    if not path:
        return "root"
    return "root/" + "/".join(str(i) for i in path)


def load_sr(file_path: str) -> pydicom.FileDataset:
    """Load a DICOM file and return the dataset. Raises on non-DICOM."""
    return pydicom.dcmread(file_path, force=False)
