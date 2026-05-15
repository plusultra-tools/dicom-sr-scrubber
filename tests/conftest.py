"""Shared test fixtures for dicom-sr-scrubber.

Builds synthetic in-memory DICOM SR datasets using pydicom.
No real patient data; no external file I/O during test collection.
"""
from __future__ import annotations

import pydicom
import pytest
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence
from pydicom.uid import generate_uid


def _make_content_item(
    value_type: str,
    relationship_type: str = "CONTAINS",
    children: list[Dataset] | None = None,
) -> Dataset:
    """Build a minimal ContentItem dataset."""
    item = Dataset()
    item.ValueType = value_type
    item.RelationshipType = relationship_type
    # Concept Name (minimal)
    cn = Dataset()
    cn.CodeValue = "121070"
    cn.CodingSchemeDesignator = "DCM"
    cn.CodeMeaning = f"Test {value_type}"
    item.ConceptNameCodeSequence = Sequence([cn])
    if children:
        item.ContentSequence = Sequence(children)
    return item


def _make_text_item(text: str, relationship_type: str = "CONTAINS") -> Dataset:
    item = _make_content_item("TEXT", relationship_type)
    item.TextValue = text
    return item


def _make_pname_item(name: str) -> Dataset:
    item = _make_content_item("PNAME")
    item.PersonName = pydicom.valuerep.PersonName(name)
    return item


def _make_date_item(date: str) -> Dataset:
    item = _make_content_item("DATE")
    item.Date = date
    return item


def _make_time_item(time: str) -> Dataset:
    item = _make_content_item("TIME")
    item.Time = time
    return item


def _make_uidref_item(uid: str) -> Dataset:
    item = _make_content_item("UIDREF")
    item.UID = uid
    return item


def _make_code_item(code_value: str = "T-D0050") -> Dataset:
    item = _make_content_item("CODE")
    cc = Dataset()
    cc.CodeValue = code_value
    cc.CodingSchemeDesignator = "SRT"
    cc.CodeMeaning = "Liver"
    item.ConceptCodeSequence = Sequence([cc])
    return item


def _make_container_item(children: list[Dataset]) -> Dataset:
    item = _make_content_item("CONTAINER")
    item.ContinuityOfContent = "SEPARATE"
    if children:
        item.ContentSequence = Sequence(children)
    return item


def build_synthetic_sr(
    patient_name: str = "Doe^John^^^",
    referring_physician: str = "Smith^Jane^^^",
    include_phi_text: bool = True,
    include_pname: bool = True,
    include_date: bool = True,
    include_time: bool = True,
    include_uidref: bool = True,
) -> pydicom.FileDataset:
    """Build a minimal synthetic DICOM SR SOP Instance (Basic Text SR).

    This does NOT use any real patient data; all values are synthetic.
    """
    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.88.11"  # Basic Text SR
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian

    ds = pydicom.FileDataset(
        filename_or_obj="synthetic.dcm",
        dataset={},
        file_meta=file_meta,
        is_implicit_VR=False,
        is_little_endian=True,
    )
    ds.is_implicit_VR = False
    ds.is_little_endian = True

    # Patient Module
    ds.PatientName = pydicom.valuerep.PersonName(patient_name)
    ds.PatientID = "SYNTH-001"
    ds.PatientBirthDate = "19800101"
    ds.PatientSex = "M"

    # General Study Module
    ds.StudyDate = "20240101"
    ds.StudyTime = "120000.000000"
    ds.AccessionNumber = "ACC-SYNTH-2024"
    ds.ReferringPhysicianName = pydicom.valuerep.PersonName(referring_physician)
    ds.StudyInstanceUID = generate_uid()
    ds.StudyID = "1"

    # General Series Module
    ds.Modality = "SR"
    ds.SeriesInstanceUID = generate_uid()
    ds.SeriesNumber = "1"

    # SR Document Module
    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.88.11"
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.InstanceNumber = "1"
    ds.CompletionFlag = "COMPLETE"
    ds.VerificationFlag = "UNVERIFIED"
    ds.ContentDate = "20240101"
    ds.ContentTime = "120000"

    # Build ContentSequence
    content_items: list[Dataset] = []

    if include_phi_text:
        # Text with PHI: SSN and name
        phi_text = _make_text_item(
            "Patient John Doe (SSN: 123-45-6789) presented with finding at ACC: ACC-SYNTH-2024."
        )
        content_items.append(phi_text)

        # Text without PHI
        clean_text = _make_text_item("No abnormalities detected in the study region.")
        content_items.append(clean_text)

    if include_pname:
        pname_item = _make_pname_item("Radiologist^James^^^")
        content_items.append(pname_item)

    if include_date:
        date_item = _make_date_item("20240101")
        content_items.append(date_item)

    if include_time:
        time_item = _make_time_item("143000.000000")
        content_items.append(time_item)

    if include_uidref:
        uid_item = _make_uidref_item(generate_uid())
        content_items.append(uid_item)

    # Code item (should always be kept)
    code_item = _make_code_item()
    content_items.append(code_item)

    # Container wrapping a nested text item
    nested_text = _make_text_item("Patient email: test@example.com")
    container = _make_container_item([nested_text])
    content_items.append(container)

    ds.ContentSequence = Sequence(content_items)

    return ds


@pytest.fixture
def synthetic_sr() -> pydicom.FileDataset:
    """Default synthetic SR with PHI in text, PNAME, DATE, TIME, UIDREF."""
    return build_synthetic_sr()


@pytest.fixture
def clean_sr() -> pydicom.FileDataset:
    """Synthetic SR with no PHI in text fields."""
    return build_synthetic_sr(
        include_phi_text=False,
        include_pname=False,
    )
