"""CLI entrypoint for dicom-sr-scrubber.

Usage:
    dicom-sr-scrubber --input path[,path...] --out dir/
                      [--profile {default,conservative}]
                      [--dry-run]
                      [--continue-on-error]
                      [--uid-salt <string>]
                      [--blacklist token,token,...]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dicom_sr_scrubber import __version__
from dicom_sr_scrubber.audit import write_audit_pack
from dicom_sr_scrubber.scrubber import scrub_files


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dicom-sr-scrubber",
        description=(
            "Parse and scrub PHI from DICOM Structured Report (SR) content trees. "
            "Emits scrubbed SR objects plus a verbatim-cited audit manifest."
        ),
    )
    p.add_argument("--version", action="version", version=f"dicom-sr-scrubber {__version__}")
    p.add_argument(
        "--input",
        required=True,
        help=(
            "Comma-separated list of DICOM SR file paths, OR a single directory. "
            "All .dcm files in a directory are processed recursively."
        ),
    )
    p.add_argument(
        "--out",
        required=True,
        help="Output directory for scrubbed files and audit manifests.",
    )
    p.add_argument(
        "--profile",
        choices=["default", "conservative"],
        default="default",
        help=(
            "Scrubbing profile. "
            "'default' redacts only TEXT items with detected PHI hits. "
            "'conservative' redacts ALL TEXT items unconditionally and strips COMPOSITE refs. "
            "(default: default)"
        ),
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Emit only the audit manifest; do not write scrubbed DICOM files.",
    )
    p.add_argument(
        "--continue-on-error",
        action="store_true",
        default=False,
        help="Log errors per file and continue rather than aborting the batch.",
    )
    p.add_argument(
        "--uid-salt",
        default="dicom-sr-scrubber-v1",
        help="Salt string for deterministic UID/PNAME hashing. Change per project for isolation.",
    )
    p.add_argument(
        "--blacklist",
        default="",
        help="Comma-separated list of name tokens to treat as PHI in TEXT fields.",
    )
    return p


def _collect_inputs(raw: str) -> list[Path]:
    """Parse the --input argument into a list of existing file paths."""
    raw = raw.strip()
    # Could be a directory
    maybe_dir = Path(raw)
    if maybe_dir.is_dir():
        return sorted(maybe_dir.rglob("*.dcm"))
    # Comma-separated list of paths
    paths: list[Path] = []
    for part in raw.split(","):
        p = Path(part.strip())
        if p.exists():
            paths.append(p)
        else:
            print(f"WARNING: input path not found, skipping: {part.strip()}", file=sys.stderr)
    return paths


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint. Returns an integer exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    input_paths = _collect_inputs(args.input)
    if not input_paths:
        print("ERROR: no valid input paths found.", file=sys.stderr)
        return 1

    out_dir = Path(args.out)
    blacklist: frozenset[str] = frozenset(
        t.strip() for t in args.blacklist.split(",") if t.strip()
    ) if args.blacklist else frozenset()

    try:
        manifest = scrub_files(
            input_paths=input_paths,
            output_dir=out_dir,
            profile_name=args.profile,
            dry_run=args.dry_run,
            continue_on_error=args.continue_on_error,
            blacklist=blacklist,
            uid_salt=args.uid_salt,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    output_paths: list[Path] = []
    if not args.dry_run:
        output_paths = [out_dir / p.name for p in input_paths if (out_dir / p.name).exists()]

    shas = write_audit_pack(manifest, input_paths, output_paths, out_dir)

    mode = " [DRY RUN]" if args.dry_run else ""
    n_redacted = sum(1 for e in manifest.entries if e.action != "KEEP")
    print(f"OK{mode}: processed {len(input_paths)} file(s), {n_redacted} item(s) modified.")
    print(f"  sr_evidence.json  sha256={shas['sr_evidence.json'][:12]}…")
    print(f"  sr_evidence.md    sha256={shas['sr_evidence.md'][:12]}…")
    print(f"  audit.sha256      sha256={shas['audit.sha256'][:12]}…")
    if args.dry_run:
        print("  (scrubbed DICOM files NOT written — dry-run mode)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
