"""Recreate the distributable source-file hash list after a reviewed release edit.

Run from the project root with: python scripts/rebuild_manifest.py
Do not run against a directory containing sensitive applicant exports.
"""
from __future__ import annotations

import hashlib
import json
import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "cv_ranker" / "build_manifest.json"
EXCLUDED_DIRS = {
    ".git", ".venv", ".pytest_cache", "__pycache__", "outputs",
    ".cv_ranker_cache", ".mypy_cache", ".ruff_cache",
}
EXCLUDED_FILES = {
    ".env", "secrets.toml", ".DS_Store", "Thumbs.db",
}
EXCLUDED_SECRET_SUFFIXES = {".key", ".pem", ".p12", ".pfx"}


def rebuild() -> int:
    info = runpy.run_path(str(ROOT / "cv_ranker" / "build_info.py"))
    files = {}
    for path in ROOT.rglob("*"):
        if not path.is_file() or path == MANIFEST:
            continue
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED_DIRS for part in relative.parts):
            continue
        if relative.name in EXCLUDED_FILES:
            continue
        if relative.name.startswith(".env.") and relative.name != ".env.example":
            continue
        if (len(relative.parts) >= 2 and relative.parts[0] == ".streamlit"
                and relative.name.startswith("secrets.")
                and relative.suffix == ".toml"):
            continue
        if relative.suffix.lower() in EXCLUDED_SECRET_SUFFIXES:
            continue
        files[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()

    data = {
        "build_id": info["BUILD_ID"],
        "assessment_protocol": info["ASSESSMENT_PROTOCOL"],
        "assessment_protocol_version": info["ASSESSMENT_PROTOCOL_VERSION"],
        "files": dict(sorted(files.items())),
    }
    MANIFEST.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return len(files)


if __name__ == "__main__":
    print(f"Hashed {rebuild()} distributable source files")
