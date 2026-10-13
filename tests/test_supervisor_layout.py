"""Deployment layout safeguards for the supervisor distribution."""
from pathlib import Path
import importlib

ROOT = Path(__file__).resolve().parents[1]

def test_root_entrypoints_and_code_imports():
    for name in ("README.md", "app.py", "main.py", "doctor.py", "run_ui.cmd", "run_supervisor_demo.cmd", "cv_ranker/build_manifest.json", "docs/ARCHITECTURE.md"):
        assert (ROOT / name).is_file(), name
    for module in ("evaluation.evaluate_benchmark", "evaluation.repeatability_probe", "evaluation.compare_benchmarks", "tools.trace_demo"):
        importlib.import_module(module)

def test_benchmark_data_not_imported_into_production():
    assert (ROOT / "evaluation" / "benchmark_cases.json").is_file()
    assert not (ROOT / "cv_ranker" / "benchmark_cases.json").exists()
