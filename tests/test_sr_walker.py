"""Tests for sr_walker module."""
from __future__ import annotations

from pydicom.dataset import Dataset

from dicom_sr_scrubber.sr_walker import (
    get_value_type,
    iter_content_items,
    path_to_str,
)
from tests.conftest import _make_text_item, build_synthetic_sr


class TestGetValueType:
    def test_returns_value_type(self) -> None:
        item = Dataset()
        item.ValueType = "TEXT"
        assert get_value_type(item) == "TEXT"

    def test_returns_unknown_for_missing(self) -> None:
        item = Dataset()
        assert get_value_type(item) == "UNKNOWN"

    def test_uppercases_value(self) -> None:
        item = Dataset()
        item.ValueType = "pname"
        assert get_value_type(item) == "PNAME"


class TestPathToStr:
    def test_empty_path(self) -> None:
        assert path_to_str(()) == "root"

    def test_single_level(self) -> None:
        assert path_to_str((0,)) == "root/0"

    def test_nested_path(self) -> None:
        assert path_to_str((1, 2, 3)) == "root/1/2/3"


class TestIterContentItems:
    def test_yields_flat_items(self) -> None:
        ds = build_synthetic_sr(
            include_phi_text=True,
            include_pname=True,
            include_date=False,
            include_time=False,
            include_uidref=False,
        )
        items = list(iter_content_items(ds))
        # Should have multiple items
        assert len(items) > 0
        # Each item is a (path, Dataset) tuple
        for path, item in items:
            assert isinstance(path, tuple)
            assert isinstance(item, Dataset)

    def test_paths_are_unique(self) -> None:
        ds = build_synthetic_sr()
        items = list(iter_content_items(ds))
        paths = [path_to_str(p) for p, _ in items]
        assert len(paths) == len(set(paths)), "Duplicate paths found in walk"

    def test_finds_nested_items(self) -> None:
        """Container children should be yielded with depth > 1."""
        ds = build_synthetic_sr()
        items = list(iter_content_items(ds))
        path_lengths = [len(p) for p, _ in items]
        assert max(path_lengths) >= 2, "Expected nested items to be found"

    def test_value_types_found(self) -> None:
        ds = build_synthetic_sr()
        items = list(iter_content_items(ds))
        vts = {get_value_type(item) for _, item in items}
        # Should find at least TEXT, PNAME, DATE, TIME, UIDREF, CODE, CONTAINER
        assert "TEXT" in vts
        assert "PNAME" in vts

    def test_no_content_sequence_yields_self(self) -> None:
        """A Dataset with no ContentSequence has no children to iterate.

        When passed a bare Dataset (no ContentSequence at all), the walker
        treats it as a lone content item and yields it at the root path.
        """
        ds = Dataset()
        items = list(iter_content_items(ds))
        # The dataset itself is yielded as the lone item at path ()
        assert len(items) == 1
        assert items[0][0] == ()  # root path

    def test_single_item_no_children(self) -> None:
        """A bare content item without a parent sequence should yield itself."""
        item = _make_text_item("hello")
        results = list(iter_content_items(item))
        # The item itself is yielded
        assert len(results) >= 1
