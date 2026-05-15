"""Quickstart example: generate a synthetic DICOM SR file for testing.

Usage:
    python generate_synthetic_sr.py [--out-dir ./output]

This script generates a synthetic Basic Text SR DICOM object with
deliberately embedded PHI patterns (all fake, not real patient data) so
you can test dicom-sr-scrubber without needing real DICOM files.

After running this script, scrub the output with:

    dicom-sr-scrubber --input ./output/synthetic_sr.dcm --out ./scrubbed/
    cat ./scrubbed/sr_evidence.md
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as a standalone script without package install
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pydicom
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence
from pydicom.uid import generate_uid, ExplicitVRLittleEndian


def _make_text_item(text: str) -> Dataset:
    item = Dataset()
    item.ValueType = "TEXT"
    item.RelationshipType = "CONTAINS"
    cn = Dataset()
    cn.CodeValue = "121070"
    cn.CodingSchemeDesignator = "DCM"
    cn.CodeMeaning = "Finding"
    item.ConceptNameCodeSequence = Sequence([cn])
    item.TextValue = text
    return item


def _make_pname_item(name: str) -> Dataset:
    item = Dataset()
    item.ValueType = "PNAME"
    item.RelationshipType = "HAS OBS CONTEXT"
    cn = Dataset()
    cn.CodeValue = "121008"
    cn.CodingSchemeDesignator = "DCM"
    cn.CodeMeaning = "Person Observer Name"
    item.ConceptNameCodeSequence = Sequence([cn])
    item.PersonName = pydicom.valuerep.PersonName(name)
    return item


def _make_date_item(date: str) -> Dataset:
    item = Dataset()
    item.ValueType = "DATE"
    item.RelationshipType = "HAS OBS CONTEXT"
    cn = Dataset()
    cn.CodeValue = "111060"
    cn.CodingSchemeDesignator = "DCM"
    cn.CodeMeaning = "Study Date"
    item.ConceptNameCodeSequence = Sequence([cn])
    item.Date = date
    return item


def _make_code_item() -> Dataset:
    item = Dataset()
    item.ValueType = "CODE"
    item.RelationshipType = "CONTAINS"
    cn = Dataset()
    cn.CodeValue = "T-D0050"
    cn.CodingSchemeDesignator = "SRT"
    cn.CodeMeaning = "Liver"
    item.ConceptNameCodeSequence = Sequence([cn])
    cc = Dataset()
    cc.CodeValue = "M-01000"
    cc.CodingSchemeDesignator = "SRT"
    cc.CodeMeaning = "Normal"
    item.ConceptCodeSequence = Sequence([cc])
    return item


def build_synthetic_sr() -> pydicom.FileDataset:
    """Build a complete synthetic Basic Text SR with deliberate PHI patterns.

    All values are fabricated; no real patient data is used.
    """
    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.88.11"
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    ds = pydicom.FileDataset(
        filename_or_obj="synthetic_sr.dcm",
        dataset={},
        file_meta=file_meta,
        is_implicit_VR=False,
        is_little_endian=True,
    )
    ds.is_implicit_VR = False
    ds.is_little_endian = True

    # --- Patient header (PHI at top level) ---
    ds.PatientName = pydicom.valuerep.PersonName("Doe^John^^^")
    ds.PatientID = "MRN: 1234567"
    ds.PatientBirthDate = "19800315"
    ds.PatientSex = "M"

    # --- Study / series ---
    ds.StudyDate = "20260515"
    ds.StudyTime = "143000.000000"
    ds.AccessionNumber = "ACC-2026-SYNTH"
    ds.ReferringPhysicianName = pydicom.valuerep.PersonName("Smith^Jane^^^")
    ds.StudyInstanceUID = generate_uid()
    ds.StudyID = "1"
    ds.Modality = "SR"
    ds.SeriesInstanceUID = generate_uid()
    ds.SeriesNumber = "1"

    # --- SR Document ---
    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.88.11"
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.InstanceNumber = "1"
    ds.CompletionFlag = "COMPLETE"
    ds.VerificationFlag = "UNVERIFIED"
    ds.ContentDate = "20260515"
    ds.ContentTime = "143000"

    # --- SR Content Tree ---
    # TEXT item with PHI: SSN embedded in clinical text
    phi_text = _make_text_item(
        "Patient John Doe (SSN: 987-65-4321, MRN: 7654321) presented on 05/15/2026. "
        "Contact: johndoe@email.com, phone +34-612-345-678. "
        "Examination of the liver shows no focal lesions. "
        "Referring physician Dr. Smith requested urgent follow-up."
    )

    # TEXT item without PHI
    clean_text = _make_text_item(
        "No acute intracranial abnormality. Ventricles and sulci are normal in size "
        "and configuration. No evidence of hemorrhage, edema, or mass effect."
    )

    # PNAME item (observer name — always PHI)
    pname = _make_pname_item("Radiologist^James^^^")

    # DATE item
    date = _make_date_item("20260515")

    # CODE item (safe — not PHI)
    code = _make_code_item()

    ds.ContentSequence = Sequence([phi_text, clean_text, pname, date, code])

    return ds


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a synthetic DICOM SR file for testing dicom-sr-scrubber."
    )
    parser.add_argument(
        "--out-dir",
        default="./output",
        help="Directory to write the synthetic SR file (default: ./output)",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "synthetic_sr.dcm"

    ds = build_synthetic_sr()
    ds.save_as(str(out_path), write_like_original=False)

    print(f"Synthetic SR written to: {out_path}")
    print()
    print("Next steps:")
    print(f"  pip install dicom-sr-scrubber")
    print(f"  dicom-sr-scrubber --input {out_path} --out ./scrubbed/ --dry-run")
    print(f"  cat ./scrubbed/sr_evidence.md")


if __name__ == "__main__":
    main()
