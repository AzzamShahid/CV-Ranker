"""Fail-fast checks that prove the intended CV Ranker build is actually loaded."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .build_info import ASSESSMENT_PROTOCOL, ASSESSMENT_PROTOCOL_VERSION, BUILD_ID
from .schemas import LLMAssessmentItem, RequirementAssessment


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def runtime_fingerprint() -> dict[str, str]:
    package_dir = Path(__file__).resolve().parent
    project_root = package_dir.parent
    assessor_path = package_dir / "assessor.py"
    segments_path = package_dir / "segments.py"
    manifest_path = package_dir / "build_manifest.json"

    if not segments_path.exists():
        raise RuntimeError(f"Stale/incomplete build: missing {segments_path}")
    if "evidence_ids" not in LLMAssessmentItem.model_fields:
        raise RuntimeError("Stale schema: LLMAssessmentItem.evidence_ids is missing")
    if "evidence_ids" not in RequirementAssessment.model_fields:
        raise RuntimeError("Stale schema: RequirementAssessment.evidence_ids is missing")

    assessor_text = assessor_path.read_text(encoding="utf-8")
    if "LLMCandidateAssessmentResponse" not in assessor_text or "render_segments" not in assessor_text:
        raise RuntimeError("Stale assessor: segment-ID assessment protocol is not active")
    if "missing, non-contextual, or irrelevant evidence" in assessor_text:
        raise RuntimeError("Stale assessor detected: legacy free-text evidence validator is still present")

    if not manifest_path.exists():
        raise RuntimeError(f"Build manifest is missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("build_id") != BUILD_ID:
        raise RuntimeError(
            f"Build manifest ID mismatch: manifest={manifest.get('build_id')!r}, runtime={BUILD_ID!r}"
        )
    if manifest.get("assessment_protocol") != ASSESSMENT_PROTOCOL:
        raise RuntimeError("Assessment protocol in build manifest does not match runtime code")
    if manifest.get("assessment_protocol_version") != ASSESSMENT_PROTOCOL_VERSION:
        raise RuntimeError("Assessment protocol version in build manifest does not match runtime code")

    files = manifest.get("files") or {}
    if not files:
        raise RuntimeError("Build manifest contains no file hashes")
    for relative, expected_hash in files.items():
        path = project_root / relative
        if not path.exists():
            raise RuntimeError(f"Build integrity failure: missing {relative}")
        actual_hash = _sha256(path)
        if actual_hash != expected_hash:
            raise RuntimeError(
                f"Build integrity failure: {relative} hash mismatch. "
                "The project folder contains mixed/stale files."
            )

    return {
        "build_id": BUILD_ID,
        "assessment_protocol": ASSESSMENT_PROTOCOL,
        "assessment_protocol_version": str(ASSESSMENT_PROTOCOL_VERSION),
        "package_path": str(package_dir),
        "manifest_files": str(len(files)),
    }


def assert_runtime_current() -> dict[str, str]:
    return runtime_fingerprint()


if __name__ == "__main__":
    info = assert_runtime_current()
    print(f"BUILD_ID={info['build_id']}")
    print(f"ASSESSMENT_PROTOCOL={info['assessment_protocol']}")
    print(f"ASSESSMENT_PROTOCOL_VERSION={info['assessment_protocol_version']}")
    print(f"MANIFEST_FILES={info['manifest_files']}")
    print(f"PACKAGE_PATH={info['package_path']}")
