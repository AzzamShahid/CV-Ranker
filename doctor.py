import argparse
import importlib
import importlib.metadata
import subprocess
import sys


REQUIRED_IMPORTS = {
    "pydantic": "pydantic",
    "yake": "yake",
    "langchain_core": "langchain-core",
    "langchain_ollama": "langchain-ollama",
    "fitz": "PyMuPDF",
    "docx": "python-docx",
    "pytest": "pytest",
    "streamlit": "streamlit",
}


def check_python() -> bool:
    print("Python")
    print("-" * 60)
    version = sys.version_info
    ok = version >= (3, 11)
    print(f"[{'OK' if ok else 'FAIL'}] Python {version.major}.{version.minor}.{version.micro}")
    return ok


def check_imports() -> bool:
    ok = True
    print("\nPython dependencies")
    print("-" * 60)
    for module, package in REQUIRED_IMPORTS.items():
        try:
            importlib.import_module(module)
            try:
                version = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                version = "installed"
            print(f"[OK] {package}: {version}")
        except Exception as exc:
            ok = False
            print(f"[MISSING] {package}: {exc}")
    return ok



def check_runtime_build() -> bool:
    print("\nCV Ranker build integrity")
    print("-" * 60)
    try:
        from cv_ranker.runtime_check import assert_runtime_current
        info = assert_runtime_current()
        print(
            f"[OK] build={info['build_id']} protocol={info['assessment_protocol']} "
            f"v{info['assessment_protocol_version']} manifest_files={info['manifest_files']}"
        )
        return True
    except Exception as exc:
        print(f"[FAIL] Runtime/build integrity check failed: {exc}")
        return False

def check_ollama(model: str) -> bool:
    print("\nOllama")
    print("-" * 60)
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        )
    except Exception as exc:
        print(f"[FAIL] Could not run 'ollama list': {exc}")
        return False
    print("[OK] Ollama CLI is available")
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    installed = {line.split()[0] for line in lines[1:] if line.split()}
    if model in installed:
        print(f"[OK] Model found: {model}")
        return True
    print(f"[FAIL] Model not found: {model}")
    print(f"Run: ollama pull {model}")
    return False


def check_structured_output(model: str) -> bool:
    print("\nLangChain/Ollama structured-output smoke test")
    print("-" * 60)
    try:
        from pydantic import BaseModel, ConfigDict
        from langchain_ollama import ChatOllama

        class HealthCheck(BaseModel):
            model_config = ConfigDict(extra="forbid", strict=True)
            ok: bool
            message: str

        llm = ChatOllama(model=model, temperature=0, client_kwargs={"timeout": 90.0})
        structured = llm.with_structured_output(HealthCheck, method="json_schema")
        result = structured.invoke(
            "Return ok=true and message='structured output works'."
        )
        print(f"[OK] {result.model_dump()}")
        return bool(result.ok)
    except Exception as exc:
        print(f"[FAIL] Structured-output call failed: {exc}")
        return False



def write_live_ranker_fixtures(root):
    """Create a legitimate small JD/CV that passes normal document validation.

    Do not relax production extraction limits to make the doctor test succeed.
    Both files exercise the normal, public pipeline from source input onward.
    """
    jd = root / "jd.txt"
    cv = root / "cv.txt"
    jd.write_text("Required Skills:\nPython\n", encoding="utf-8")
    cv.write_text(
        "Professional Summary:\n"
        "Software developer with practical experience building production Python applications.\n"
        "Technical Skills:\n"
        "Python\n"
        "Professional Experience:\n"
        "Developed and maintained Python backend services for customer applications.\n",
        encoding="utf-8",
    )
    return jd, cv


def check_ranker_contract(model: str) -> bool:
    """Run a tiny real JD -> CV -> evidence_ids -> score contract test."""
    print("\nLive CV Ranker pipeline contract")
    print("-" * 60)
    try:
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from cv_ranker.config import Settings
        from cv_ranker.pipeline import CVRanker

        with TemporaryDirectory(prefix="cv_ranker_doctor_") as tmp:
            root = Path(tmp)
            jd, cv = write_live_ranker_fixtures(root)
            report = CVRanker(
                Settings(model_name=model, max_requirements=5, assessment_batch_size=5),
                use_llm=True,
            ).run(jd, [cv])

        if len(report.requirements) != 1 or report.requirements[0].name.casefold() != "python":
            raise RuntimeError(f"Expected one frozen Python requirement, got {report.requirements}")
        candidate = report.candidates[0]
        if candidate.primary_score != 100.0 or candidate.matched_primary != 1:
            raise RuntimeError(
                f"Expected 1/1 matched and score=100, got {candidate.matched_primary}/{candidate.total_primary} "
                f"score={candidate.primary_score}; candidate_errors={candidate.errors}; "
                f"jd_mode={report.jd_validation_mode}; warnings={report.warnings}"
            )
        assessment = candidate.assessments[0]
        if not assessment.evidence_ids or not assessment.evidence:
            raise RuntimeError("Evidence segment IDs/source text were not produced by the live pipeline")
        print(
            f"[OK] JD mode={report.jd_validation_mode}; candidate mode={candidate.evaluation_mode}; "
            f"score={candidate.primary_score:.2f}%; evidence_ids={assessment.evidence_ids}"
        )
        return True
    except Exception as exc:
        print(f"[FAIL] Live ranking contract failed: {exc}")
        return False

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen2.5:3b")
    parser.add_argument("--live", action="store_true", help="Also make one live structured LLM call")
    args = parser.parse_args()

    python_ok = check_python()
    imports_ok = check_imports()
    runtime_ok = check_runtime_build() if python_ok and imports_ok else False
    ollama_ok = check_ollama(args.model) if runtime_ok else False
    live_ok = True
    if args.live and python_ok and imports_ok and ollama_ok:
        live_ok = check_structured_output(args.model)
        if live_ok:
            live_ok = check_ranker_contract(args.model)

    print("\nOverall")
    print("-" * 60)
    ready = python_ok and imports_ok and runtime_ok and ollama_ok and live_ok
    print("READY" if ready else "NOT READY - see failures above")
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
