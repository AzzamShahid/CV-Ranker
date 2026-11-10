"""Package ONLY hashed release files; never include .env, .venv or user outputs.

Usage: python scripts/package_source_release.py ABSOLUTE_OUTPUT_ZIP
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "cv_ranker" / "build_manifest.json"
PACKAGE_FOLDER = "CV_Ranker_Supervisor_Edition"


def main(output_name: str) -> int:
    destination = Path(output_name).resolve()
    if not destination.is_absolute() or destination.is_relative_to(ROOT):
        raise ValueError("Output ZIP must be an absolute path outside the release source directory")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    items = list(manifest["files"].items())
    if not items:
        raise RuntimeError("Missing source release manifest")
    with ZipFile(destination, mode="w", compression=ZIP_DEFLATED, compresslevel=8) as archive:
        for relative, expected in items:
            candidate = (ROOT / relative).resolve()
            if not candidate.is_relative_to(ROOT) or not candidate.is_file():
                raise RuntimeError(f"Invalid manifest entry: {relative}")
            if hashlib.sha256(candidate.read_bytes()).hexdigest() != expected:
                raise RuntimeError(f"Source changed after manifest build: {relative}")
            archive.write(candidate, f"{PACKAGE_FOLDER}/{relative}")
        archive.write(MANIFEST, f"{PACKAGE_FOLDER}/cv_ranker/build_manifest.json")
    with ZipFile(destination) as archive:
        failed = archive.testzip()
        if failed is not None:
            raise RuntimeError(f"ZIP integrity failure: {failed}")
        if len(archive.namelist()) != len(items) + 1:
            raise RuntimeError("Archive does not match hashed file inventory")
    print(f"Package: {destination}")
    print(f"Verified source entries: {len(items)} + build manifest")
    print(f"Size: {destination.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Expected one absolute output ZIP path")
    raise SystemExit(main(sys.argv[1]))
