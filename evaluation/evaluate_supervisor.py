"""Offline SUPERVISOR unified-engine contract smoke test.

Unlike evaluate_industrial (legacy/fallback), this invokes the very same
CVRanker(unified=True) branch as the Streamlit supervisor. A deterministic
model double tests Python source validation, specialists, reconciliation,
weighted scoring and ZIP, NOT live LLM semantic accuracy. Labels are fictional
engineering controls, not a blind human-adjudicated benchmark.

Run: python -m evaluation.evaluate_supervisor --output /tmp/supervisor.json
"""
from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile

import numpy as np

from cv_ranker.config import Settings
from cv_ranker.eligibility import jd_source_sha256
from cv_ranker.pipeline import CVRanker
from cv_ranker.requirement_typing import classify_requirement
from cv_ranker.report_bundle import complete_results_zip
from cv_ranker.schemas import JDReviewDraft, ValidatedRequirement
from cv_ranker.unified import UnifiedItem, UnifiedResponse
from cv_ranker.weighted_scoring import ScoreWeights, weighted_leaderboard, allocation_bucket


class SyntheticEncoder:
    fingerprint = "v4962-supervisor-offline-smoke"

    def embed_documents(self, values):
        return np.ones((len(values), 3), dtype=np.float32)

    def embed_queries(self, values):
        return np.ones((len(values), 3), dtype=np.float32)


class SyntheticProvider:
    disabled_reason = None
    http_attempts = 0
    http_429_count = 0
    token_usage: dict = {}

    def __init__(self, settings, *, declared_decision: str = "found"):
        self.settings = settings
        self.calls = 0
        self.declared_decision = declared_decision

    def prompt_fits(self, system_prompt, user_prompt):
        return True

    def invoke_structured(self, *, system_prompt, user_prompt, schema):
        self.calls += 1
        if schema.__name__ == "IndependentSemanticDecisionByID":
            return schema.model_validate({"R001": {
                "decision": "not_found", "relation": "absent",
                "evidence_ids": [], "proof_excerpt": None,
                "reason": "No supported direct or adjacent capability after original-source review.",
            }})
        packet = json.loads(user_prompt)
        sources = packet.get("sources", [])
        ids = [s["id"] for s in sources]
        source_id = ids[0] if ids else None
        return UnifiedResponse(assessments=[UnifiedItem(
            requirement_id="R001", decision=self.declared_decision,
            relation="direct" if self.declared_decision == "found" else "absent",
            evidence_ids=[source_id] if source_id and self.declared_decision == "found" else [],
            reason=("Provider proposed the citation as direct; deterministic validators "
                    "must independently accept or reject the original source."),
        )])


# Independent expected labels for invented single-source engineering controls.
# A deliberately mistaken positive MODEL PROPOSAL is included in the negative.
CASES = [
    ("erp_false_initialism", "Use ERP for production reporting.",
     "Managed equipment repair procedures for production reporting.", "Not Found"),
    ("erp_three_way", "Use ERP, MES or SAP for production reporting.",
     "Used ERP dashboards for production reporting.", "Found"),
    ("mes_three_way", "Use ERP, MES or SAP for production reporting.",
     "Used MES dashboards for production reporting.", "Found"),
    ("sap_three_way", "Use ERP, MES or SAP for production reporting.",
     "Used SAP dashboards for production reporting.", "Found"),
    ("erp_mes", "Use ERP or manufacturing execution systems (MES) for weaving production reporting.",
     "Used ERP dashboards for weaving production reporting.", "Found"),
    ("mes_expanded", "Use ERP or manufacturing execution systems (MES) for weaving production reporting.",
     "Used manufacturing execution systems for weaving production reporting.", "Found"),
    ("crm_two_way", "Use CRM or ERP for client reporting.",
     "Used CRM to prepare client reports.", "Found"),
]


# Cross-domain adversarial controls deliberately use a provider stub that
# proposes Found even for unrelated performed work. The source validator must
# not award full credit just because a correct S ID contains an action verb.
# These are independent fictional engineering controls, not human gold labels.
CROSS_DOMAIN_CASES = [
    ("qa_completed_work", "Investigate flaky CI tests and document root causes.",
     "Investigated flaky CI tests and documented root causes.", "Found"),
    ("qa_unrelated_work", "Investigate flaky CI tests and document root causes.",
     "Built customer reporting dashboards in Excel.", "Not Found"),
    ("finance_completed_reconciliation", "Reconcile monthly general ledger entries.",
     "Reconciled monthly general ledger entries.", "Found"),
    ("finance_unrelated_logistics", "Reconcile monthly general ledger entries.",
     "Operated warehouse forklift machinery for monthly shipments.", "Not Found"),
    ("hr_completed_onboarding", "Coordinate employee onboarding paperwork.",
     "Coordinated employee onboarding paperwork for new joiners.", "Found"),
    ("logistics_completed_dispatch", "Prepare vehicle dispatch schedules.",
     "Prepared vehicle dispatch schedules for daily deliveries.", "Found"),
    ("healthcare_completed_scheduling", "Document patient appointment schedules.",
     "Documented patient appointment schedules for the clinic.", "Found"),
    ("healthcare_unrelated_storage", "Document patient appointment schedules.",
     "Maintained warehouse storage shelves and inventory.", "Not Found"),
    ("network_completed_vlan", "Configure VLANs on managed switches.",
     "Configured VLANs on managed switches for regional office.", "Found"),
    ("network_unrelated_facilities", "Configure VLANs on managed switches.",
     "Coordinated office staff and facility cleaning.", "Not Found"),
    ("maintenance_completed_safety", "Inspect conveyor belt safety guards.",
     "Inspected conveyor belt safety guards and recorded defects.", "Found"),
    ("maintenance_unrelated_invoicing", "Inspect conveyor belt safety guards.",
     "Repaired office invoices with spreadsheet validation.", "Not Found"),
    ("licensing_negative", "Hold a valid nursing license.",
     "Completed public health university coursework, no nursing license.", "Not Found"),
    ("education_higher_same_field", "Completed Bachelor's degree in Computer Science.",
     "Completed Master of Science in Computer Science awarded 2023.", "Found"),
    ("education_wrong_field", "Completed Bachelor's degree in Computer Science.",
     "Master of Chemistry degree completed 2023.", "Not Found"),
]


def run_suite(cases=None) -> dict:
    suite_cases = CASES if cases is None else cases
    observations = []
    with TemporaryDirectory(prefix="cvr-supervisor-smoke-") as temp:
        root = Path(temp)
        for index, (name, jd, resume, expected) in enumerate(suite_cases):
            folder = root / name
            folder.mkdir()
            jd_file = folder / "jd.txt"
            cv_file = folder / "fictional_cv.txt"
            jd_file.write_text(jd, encoding="utf-8")
            cv_file.write_text("Experience:\n" + resume, encoding="utf-8")
            base = ValidatedRequirement(requirement_id="R001", name=jd,
                                        jd_evidence=jd, priority="required")
            req = base.model_copy(update={"constraint": classify_requirement(base, jd)})
            reviewed = JDReviewDraft(jd_sha256=jd_source_sha256(jd),
                                     yake_candidates=[], requirements=[req],
                                     jd_validation_mode="manual", approved=True)
            settings = Settings(llm_provider="ollama")
            provider = SyntheticProvider(settings)
            with patch("cv_ranker.pipeline.StructuredLLM", return_value=provider):
                ranker = CVRanker(settings=settings, use_llm=True, unified=True,
                                  embedding_encoder=SyntheticEncoder(),
                                  embedding_cache_path=folder / "embeddings.sqlite")
                report = ranker.run(jd_file, [cv_file], approved_jd=reviewed)
            assert ranker.unified and ranker.use_llm, "Silent fallback is forbidden"
            candidate = report.candidates[0]
            row = candidate.assessments[0] if candidate.assessments else None
            decision = ("Unverified" if row and row.assessment_state == "unverified" else
                        row.unified_status if row else "Unverified")
            # Give the one frozen criterion its *actual* category's 100
            # points. A degree scored with education=0 would be Unavailable,
            # which is a test setup error rather than a CV decision failure.
            bucket = allocation_bucket(req)
            weights = ScoreWeights(experience=100 if bucket == "experience" else 0,
                                   education=100 if bucket == "education" else 0,
                                   jd=100 if bucket == "jd" else 0)
            leaderboard = weighted_leaderboard(report, weights)
            archive = ZipFile(io.BytesIO(complete_results_zip(report, weights)))
            exported = list(csv.DictReader(io.StringIO(
                archive.read("weighted_leaderboard.csv").decode("utf-8-sig"))))[0]
            observation = {
                "case": name, "expected": expected, "observed": decision,
                "score": leaderboard[0]["weighted_score"],
                "score_status": exported["Score status"],
                "accepted_original_ids": row.evidence_ids if row else [],
                "model_calls": provider.calls,
                "correct": decision == expected,
                "engine": "CVRanker(unified=True) with controlled provider",
                "provider": "deterministic_stub_no_external_calls",
            }
            observations.append(observation)
    return {"scope": ("offline_supervisor_unified_engine_adversarial_cross_domain_not_live_accuracy"
                      if cases is not None else
                      "offline_supervisor_unified_engine_smoke_not_live_accuracy"),
            "count": len(observations),
            "correct": sum(x["correct"] for x in observations),
            "cases": observations}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--cross-domain", action="store_true",
                        help="15 fictional cross-domain adversarial supervisor-path cases")
    args = parser.parse_args(argv)
    report = run_suite(CROSS_DOMAIN_CASES if args.cross_domain else None)
    rendered = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["correct"] == report["count"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
