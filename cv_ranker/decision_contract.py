"""Application-owned current decision and processing contract (protocol 56 candidate).

This module intentionally has no LLM functions: a model may propose a
source-grounded verdict, but only the workflow may certify completion.
"""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

Verdict = Literal["Found", "Transferable", "Not Found"]
ProcessingState = Literal["pending", "running", "completed", "paused", "failed", "input_required"]
FailureCode = Literal[
    "provider_rate_limit", "provider_timeout", "provider_authentication",
    "provider_unavailable", "response_schema_invalid", "response_row_missing",
    "citation_identity_invalid", "document_unreadable", "source_coverage_incomplete",
    "semantic_review_incomplete", "semantic_adjudication_required",
    "result_store_unrecoverable", "provider_unknown_delivery",
    "source_identity_invalid", "processing_error",
]

class ProcessingFailure(StrictModel):
    code: FailureCode
    stage: str = Field(min_length=1)
    detail: str = Field(min_length=1)
    retry_eligible: bool = False
    operation_reference: str | None = None

class DecisionRecord(StrictModel):
    verdict: Verdict | None = None
    processing_state: ProcessingState
    failure: ProcessingFailure | None = None
    explanation: str = ""

    @model_validator(mode="after")
    def consistency(self):
        if self.processing_state == "completed":
            if self.verdict is None or self.failure is not None:
                raise ValueError("A completed assessment requires one verdict, and no execution failure")
        elif self.verdict is not None:
            raise ValueError("An unfinished assessment cannot issue a final verdict")
        if self.failure is not None and self.processing_state == "completed":
            raise ValueError("Completed judgments cannot carry a processing failure")
        return self


def completed(verdict: Verdict, reason: str = "") -> DecisionRecord:
    return DecisionRecord(verdict=verdict, processing_state="completed", explanation=reason)


def incomplete(code: FailureCode, *, stage: str, detail: str,
               processing_state: Literal["paused", "failed", "input_required"] = "failed",
               retry_eligible: bool = False,
               operation_reference: str | None = None) -> DecisionRecord:
    return DecisionRecord(processing_state=processing_state,
                          failure=ProcessingFailure(code=code, stage=stage,
                          detail=detail, retry_eligible=retry_eligible,
                          operation_reference=operation_reference))
