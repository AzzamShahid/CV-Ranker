"""Record structured Qwen answers before deterministic CV assessment validation.

This wrapper is used by the benchmark only. It delegates model calls unchanged,
and stores only structured outputs, never prompts, CV text, or model internals.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any


class RecordingLLM:
    def __init__(self, delegate: Any):
        self.delegate = delegate
        self.assessment_calls: list[dict] = []
        self.jd_calls: int = 0

    def __getattr__(self, name: str) -> Any:
        return getattr(self.delegate, name)

    def invoke_structured(self, *, system_prompt: str, user_prompt: str, schema: Any) -> Any:
        result = self.delegate.invoke_structured(
            system_prompt=system_prompt, user_prompt=user_prompt, schema=schema
        )
        if hasattr(result, "assessments"):
            phase = (
                "focused_abbreviation" if user_prompt.startswith("SECOND LOOK FOCUSED ABBREVIATION")
                else "second_look" if user_prompt.startswith("SECOND LOOK")
                else "correction" if "correcting invalid rows" in system_prompt.casefold()
                else "initial"
            )
            self.assessment_calls.append({
                "phase": phase,
                "rows": [
                    {
                        "requirement_id": item.requirement_id,
                        "status": item.status,
                        "evidence_ids": list(getattr(item, "evidence_ids", []) or []),
                        "matched_term": getattr(item, "matched_term", None),
                    }
                    for item in result.assessments
                ],
            })
        else:
            self.jd_calls += 1
        return result

    def observations(self) -> dict[str, dict]:
        """Group model attempts by frozen requirement ID, preserving call order."""
        by_id: dict[str, list[dict]] = defaultdict(list)
        for call_index, call in enumerate(self.assessment_calls):
            for item in call["rows"]:
                by_id[item["requirement_id"]].append({
                    **item,
                    "phase": call["phase"],
                    "call_index": call_index,
                })
        return {
            key: {
                "first_status": attempts[0]["status"],
                "last_status": attempts[-1]["status"],
                "last_evidence_ids": attempts[-1]["evidence_ids"],
                "last_matched_term": attempts[-1]["matched_term"],
                "attempts": len(attempts),
                "retried": any(a["phase"] == "correction" for a in attempts),
                "second_look": any(a["phase"] in {"second_look", "focused_abbreviation"} for a in attempts),
                "focused_abbreviation": any(a["phase"] == "focused_abbreviation" for a in attempts),
                # Capture model proposals without whole CVs or full prompts.
                # Quoted matched terms are source-derived and must be handled privately.
                "attempt_history": [
                    {
                        "phase": attempt["phase"],
                        "status": attempt["status"],
                        "evidence_ids": list(attempt["evidence_ids"]),
                        "matched_term": attempt["matched_term"],
                        "call_index": attempt["call_index"],
                    }
                    for attempt in attempts
                ],
            }
            for key, attempts in by_id.items()
        }
