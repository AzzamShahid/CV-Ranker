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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen2.5:3b")
    parser.add_argument("--live", action="store_true", help="Also make one live structured LLM call")
    args = parser.parse_args()

    python_ok = check_python()
    imports_ok = check_imports()
    ollama_ok = check_ollama(args.model)
    live_ok = True
    if args.live and python_ok and imports_ok and ollama_ok:
        live_ok = check_structured_output(args.model)

    print("\nOverall")
    print("-" * 60)
    ready = python_ok and imports_ok and ollama_ok and live_ok
    print("READY" if ready else "NOT READY - see failures above")
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
