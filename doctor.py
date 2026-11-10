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
    "dotenv": "python-dotenv",
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


def check_structured_output(settings) -> bool:
    print("\nLangChain/Ollama structured-output smoke test")
    print("-" * 60)
    try:
        from pydantic import BaseModel, ConfigDict
        from cv_ranker.llm import StructuredLLM

        class HealthCheck(BaseModel):
            model_config = ConfigDict(extra="forbid", strict=True)
            ok: bool
            message: str

        result = StructuredLLM(settings).invoke_structured(
            system_prompt="Return a structured JSON response matching the supplied schema.",
            user_prompt="Return ok=true and message='structured output works'.",
            schema=HealthCheck,
        )
        print(f"[OK] {result.model_dump()}")
        return bool(result.ok)
    except Exception as exc:
        print(f"[FAIL] Structured-output call failed: {exc}")
        return False



def check_openrouter_structured_output(settings) -> bool:
    print("\nOpenRouter structured-output smoke test (synthetic data only)")
    print("-" * 60)
    try:
        from pydantic import BaseModel, ConfigDict
        from cv_ranker.llm import StructuredLLM

        class HealthCheck(BaseModel):
            model_config = ConfigDict(extra="forbid", strict=True)
            ok: bool
            message: str

        result = StructuredLLM(settings).invoke_structured(
            system_prompt="Return only a structured JSON response matching the supplied schema.",
            user_prompt="Return ok=true and message='structured output works'.",
            schema=HealthCheck,
        )
        print("[OK] OpenRouter returned schema-validated JSON")
        return result.ok is True
    except Exception as exc:
        print(f"[FAIL] OpenRouter structured call failed: {type(exc).__name__}")
        return False


def write_live_ranker_fixtures(root):
    """Create a legitimate small JD/CV that passes normal document validation.

    Do not relax production extraction limits to make the doctor test succeed.
    Both files exercise the normal, public pipeline from source input onward.
    """
    jd = root / "jd.txt"
    cv = root / "cv.txt"
    jd.write_text(
        "Required Skills:\n"
        "Python\n"
        "Spreadsheet reporting\n"
        "Customer support\n", encoding="utf-8")
    cv.write_text(
        "Professional Summary:\n"
        "Software developer with practical experience building production Python applications.\n"
        "Technical Skills:\n"
        "Python\n"
        "Spreadsheet reporting\n"
        "Customer support\n"
        "Professional Experience:\n"
        "Developed and maintained Python backend services for customer applications.\n"
        "Created spreadsheet reports for monthly business reviews.\n"
        "Provided customer support and resolved service requests.\n",
        encoding="utf-8",
    )
    return jd, cv


def check_ranker_contract(model: str, settings=None) -> bool:
    """Exercise the actual retrieval-first live pipeline, not the legacy path."""
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
                Settings(model_name=model, max_requirements=5, assessment_batch_size=5, llm_provider=settings.llm_provider if settings is not None else "ollama"),
                use_llm=True, unified=True,
            ).run(jd, [cv])

        required_names = {"python", "spreadsheet reporting", "customer support"}
        if len(report.requirements) != 3 or {
                item.name.casefold() for item in report.requirements} != required_names:
            raise RuntimeError(f"Expected three separate cross-functional requirements, got {report.requirements}")
        candidate = report.candidates[0]
        if candidate.primary_score != 100.0 or candidate.matched_primary != 3:
            raise RuntimeError(
                f"Expected 3/3 matched and score=100, got {candidate.matched_primary}/{candidate.total_primary} "
                f"score={candidate.primary_score}; candidate_errors={candidate.errors}; "
                f"jd_mode={report.jd_validation_mode}; warnings={report.warnings}"
            )
        if len(candidate.assessments) != 3 or any(
                not item.evidence_ids or not item.evidence or item.unified_status != "Found"
                for item in candidate.assessments):
            raise RuntimeError("Evidence segment IDs/source text were not produced by the live pipeline")
        if any(item.assessment_state == "unverified" for item in candidate.assessments):
            raise RuntimeError("The live model left a criterion technically unverified")
        print(
            f"[OK] JD mode={report.jd_validation_mode}; candidate mode={candidate.evaluation_mode}; "
            f"score={candidate.primary_score:.2f}%; "
            f"criteria={len(candidate.assessments)}, all source-grounded"
        )
        return True
    except Exception as exc:
        print(f"[FAIL] Live ranking contract failed: {exc}")
        return False

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=("openrouter", "ollama"), default=None,
                        help="Test Cloud or Local independently of the .env default/UI selection")
    parser.add_argument("--model", default=None, help="Optional command-line model override for diagnostic runs")
    parser.add_argument("--live", action="store_true", help="Make a paid/provider live structured test and small synthetic JD/CV run")
    args = parser.parse_args()

    python_ok = check_python()
    imports_ok = check_imports()
    runtime_ok = check_runtime_build() if python_ok and imports_ok else False
    provider_ok = False
    live_ok = True
    settings = None
    if runtime_ok:
        try:
            from cv_ranker.config import Settings
            config_overrides = {}
            if args.provider:
                config_overrides["llm_provider"] = args.provider
            if args.model:
                config_overrides["model_name"] = args.model
            settings = Settings(**config_overrides)
            print(f"\nLLM provider: {settings.llm_provider} • model: {settings.model_name}")
            if settings.llm_provider == "ollama":
                provider_ok = check_ollama(settings.model_name)
            else:
                provider_ok = True  # Configuration checked; network is verified by --live
                print("[OK] OpenRouter credentials configured (not yet network-verified)")
                print("Ollama remains required separately for EmbeddingGemma retrieval")
        except ValueError as exc:
            print(f"[FAIL] LLM configuration: {exc}")
    if args.live and python_ok and imports_ok and provider_ok and settings is not None:
        if settings.llm_provider == "openrouter":
            live_ok = check_openrouter_structured_output(settings)
        else:
            live_ok = check_structured_output(settings)
        if live_ok:
            live_ok = check_ranker_contract(settings.model_name, settings)

    print("\nOverall")
    print("-" * 60)
    ready = python_ok and imports_ok and runtime_ok and provider_ok and live_ok
    if ready and not args.live:
        print("LOCAL CHECKS PASS; LIVE RETRIEVAL + MODEL CONTRACT NOT TESTED (rerun --live)")
    else:
        print("LIVE CONTRACT PASS" if ready else "NOT READY - see failures above")
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
