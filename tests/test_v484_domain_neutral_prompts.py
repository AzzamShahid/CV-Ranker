"""Prompt neutrality: no department or named-skill matching examples in runtime prompts."""
import ast
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1] / "cv_ranker"


def _runtime_prompts():
    prompts = {}
    for path in ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            value = node.value
            if (isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute)
                    and value.func.attr == "strip" and not value.args):
                value = value.func.value
            if not (isinstance(value, ast.Constant) and isinstance(value.value, str)):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and "PROMPT" in target.id:
                    prompts[f"{path.relative_to(ROOT)}:{target.id}"] = value.value
    return prompts


def test_all_literal_model_prompts_avoid_fixed_professional_examples():
    prompts = _runtime_prompts()
    assert len(prompts) >= 8
    specific_names = (
        "LangChain", "LangGraph", "Haystack", "PyTorch", "TensorFlow",
        "GCP", "Google Cloud", "FastAPI", "Django", "time-series",
        "forecasting", "neural", "transformer", "machine learning",
        "deep learning",
    )
    offenders = {label: [term for term in specific_names
                          if re.search(r"(?<![\w-])" + re.escape(term) + r"(?![\w-])",
                                       prompt, re.I)]
                 for label, prompt in prompts.items()}
    assert not {label: terms for label, terms in offenders.items() if terms}, offenders


def test_unified_contract_is_decision_based_and_source_grounded():
    source = (ROOT / "unified.py").read_text(encoding="utf-8")
    from cv_ranker.unified import UNIFIED_PROMPT
    required = ("found", "transferable", "not_found", "uncertain",
                "FROZEN JD", "ENTAILMENT CHECK", "all supplied sources",
                "performed work", "denial", "including/such as",
                "AND", "VERBATIM", "source IDs")
    normalized = " ".join(UNIFIED_PROMPT.casefold().split())
    for term in required:
        assert term.casefold() in normalized, term
    assert '"Time-series anomaly screening' not in source
    assert "BM25" not in source
    # Normal and corrective calls retain one required-ID schema. Unresolved
    # semantic judgments use one separate grouped, contrastive adjudicator,
    # never a per-requirement call or a retry with the original contract.
    assert source.count("_invoke_required_id_group(") == 3
    assert source.count("_independently_adjudicate(") == 2
    assert source.count("llm.invoke_structured(") == 2  # standard + independent grouped contract


def test_jd_alternative_and_validation_prompts_are_domain_neutral():
    from cv_ranker.jd import SYSTEM_PROMPT, CORRECTION_PROMPT
    from cv_ranker.assessor import SYSTEM_PROMPT as LEGACY_PROMPT
    assert '"A or B"' in SYSTEM_PROMPT
    assert "including" in SYSTEM_PROMPT and "including" in CORRECTION_PROMPT
    assert "DIFFERENT item" in LEGACY_PROMPT
    assert "Do not give transferable credit" in LEGACY_PROMPT
