"""Human approval of source-grounded JD extraction, independent of CV scoring."""
from __future__ import annotations

import json

from .jd_expression import validate_expression
from .schemas import JDConditionNode
from .requirement_typing import classify_requirement
from .jd_coverage import explicit_clause_coverage, coverage_warning
from .schemas import JDReviewDraft, RequirementConstraint, ValidatedRequirement
from .text_utils import evidence_exists


def editable_jd_rows(draft: JDReviewDraft) -> list[dict]:
    return [{
        "ID": item.requirement_id,
        "Priority": item.priority,
        "Requirement": item.name,
        "Type": item.constraint.kind,
        "JD source": item.jd_evidence,
        "Minimum years": item.constraint.minimum_years,
        "Degree level": item.constraint.degree_level or "",
        "Field of study": item.constraint.field_of_study or "",
        "Evidence standard": item.constraint.evidence_modality or "Needs review",
        "Duration subject": item.constraint.duration_subject or "",
        "Mandatory JD parts": " | ".join(item.constraint.approved_mandatory_parts),
        "Alternative groups JSON": json.dumps(item.constraint.approved_alternative_groups, ensure_ascii=False)
        if item.constraint.approved_alternative_groups else "",
        "Complete JD expression JSON": (json.dumps(item.constraint.approved_expression.model_dump(), ensure_ascii=False)
            if item.constraint.approved_expression is not None else ""),
    } for item in draft.requirements]


def approve_jd_rows(*, draft: JDReviewDraft, rows: list[dict],
                    jd_text: str, max_requirements: int) -> JDReviewDraft:
    """Validate the review table and freeze exactly what the evaluator approved.

    Every included row retains a literal JD quotation. Manual priority, name,
    kind and added/deleted rows are permitted; no invented JD evidence is.
    Typed numerical/degree constraints are always regenerated from the quote.
    """
    if not rows:
        raise ValueError("Keep at least one job requirement before approval.")
    if len(rows) > max_requirements:
        raise ValueError(f"At most {max_requirements} JD requirements can be approved.")
    originals = {r.requirement_id: r for r in draft.requirements}
    ids = set()
    next_id = 1
    for old_id in originals:
        if old_id.startswith("R") and old_id[1:].isdigit():
            next_id = max(next_id, int(old_id[1:]) + 1)
    approved = []
    edited = len(rows) != len(draft.requirements)
    for i, item in enumerate(rows, 1):
        name = str(item.get("Requirement") or "").strip()
        priority = str(item.get("Priority") or "").strip().lower()
        kind = str(item.get("Type") or "").strip().lower()
        quotation = str(item.get("JD source") or "").strip()
        row_id = str(item.get("ID") or "").strip()
        if not name or not quotation:
            raise ValueError(f"JD row {i}: requirement name and exact JD source are required.")
        if priority not in {"required", "preferred", "unknown"}:
            raise ValueError(f"JD row {i}: select a valid priority.")
        if not evidence_exists(quotation, jd_text):
            raise ValueError(f"JD row {i}: the JD source must quote the actual uploaded JD text.")
        if row_id and row_id not in originals:
            raise ValueError(f"JD row {i}: unknown requirement ID; leave ID blank for a new row.")
        if not row_id:
            row_id = f"R{next_id:03d}"
            next_id += 1
        if row_id in ids:
            raise ValueError(f"JD row {i}: duplicate requirement ID {row_id}.")
        ids.add(row_id)
        old = originals.get(row_id)
        base = ValidatedRequirement(requirement_id=row_id, name=name,
                                    priority=priority, jd_evidence=quotation)
        inferred = (old.constraint if old and old.name == name
                    and old.jd_evidence == quotation
                    and old.constraint.kind == kind
                    else classify_requirement(base, jd_text))
        if kind and kind != inferred.kind:
            if kind not in RequirementConstraint.model_fields["kind"].annotation.__args__:
                raise ValueError(f"JD row {i}: invalid criterion type.")
            # A supervisor can correct classification, but a type override
            # cannot manufacture degree/year facts absent from the quotation.
            manually_selected_modality = {
                "skill": "knowledge_claim", "responsibility": "performed_work",
                "experience": ("dated_professional_tenure" if inferred.minimum_years
                               is not None else "performed_work"),
                "education": "completed_qualification",
                "certification": "credential_claim", "license": "credential_claim",
                "eligibility": "eligibility_condition", "other": "employer_review_required",
            }[kind]
            inferred = inferred.model_copy(update={
                "kind": kind,
                "minimum_years": inferred.minimum_years if kind == "experience" else None,
                "degree_level": inferred.degree_level if kind == "education" else None,
                "field_of_study": inferred.field_of_study if kind == "education" else None,
                "evidence_modality": manually_selected_modality,
                "duration_subject": ("candidate_tenure" if kind == "experience"
                                     and inferred.minimum_years is not None else
                                     "none" if inferred.minimum_years is None else
                                     "non_tenure_timeframe_review"),
                "origin": "manual_review_pending", "requires_review": True,
            })
        # Optional explicit employer-condition review. JD strings are
        # original EXACT spans; this is not a synonym catalogue or a new
        # scored requirement. Empty fields preserve previous unreviewed
        # semantics unless an earlier mapping was deliberately cleared.
        raw_parts = item.get("Mandatory JD parts", None)
        raw_groups = item.get("Alternative groups JSON", None)
        if raw_parts is not None or raw_groups is not None:
            parts = ([x.strip() for x in str(raw_parts or "").split("|") if x.strip()]
                     if raw_parts is not None else list(inferred.approved_mandatory_parts))
            try:
                groups = (json.loads(str(raw_groups)) if str(raw_groups or "").strip()
                          else [] if raw_groups is not None
                          else list(inferred.approved_alternative_groups))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"JD row {i}: Alternative groups must be valid JSON.") from exc
            if not isinstance(groups, list) or any(not isinstance(g, list) or
                any(not isinstance(a, str) for a in g) for g in groups):
                raise ValueError(f"JD row {i}: Alternative groups must be a list of lists of JD text.")
            for fragment in [*parts, *(a for group in groups for a in group)]:
                if not evidence_exists(fragment, quotation):
                    raise ValueError(f"JD row {i}: condition fragment is not quoted in the frozen JD: {fragment!r}")
            inferred = RequirementConstraint.model_validate({
                **inferred.model_dump(),
                "approved_mandatory_parts": parts,
                "approved_alternative_groups": groups,
                "requires_review": False if parts or groups else inferred.requires_review,
            })
        raw_expression = item.get("Complete JD expression JSON", None)
        if raw_expression is not None:
            try:
                tree = (JDConditionNode.model_validate(json.loads(str(raw_expression)))
                        if str(raw_expression or "").strip() else None)
            except (ValueError, TypeError) as exc:
                raise ValueError(f"JD row {i}: invalid complete expression JSON") from exc
            if tree is not None:
                validate_expression(tree, quotation)
            inferred = RequirementConstraint.model_validate({
                **inferred.model_dump(), "approved_expression": tree,
                "requires_review": False if tree is not None else inferred.requires_review})
        requirement = base.model_copy(update={"constraint": RequirementConstraint.model_validate(inferred)})
        approved.append(requirement)
        if old != requirement:
            edited = True
    # Approval may add, delete or merge R rows. Recompute the original JD
    # source coverage from the approved rows rather than retaining stale
    # extraction-time claims. Coverage signals review; it never fabricates R.
    coverage = explicit_clause_coverage(jd_text, approved)
    updated_warnings = [x for x in draft.warnings
                        if not x.startswith("JD source-coverage review:")]
    warning = coverage_warning(coverage)
    if warning:
        updated_warnings.append(warning)
    diagnostics = [x for x in draft.diagnostics
                   if x.get("stage") != "explicit_jd_clause_coverage"]
    return draft.model_copy(update={
        "requirements": approved, "approved": True,
        "edited": edited, "warnings": updated_warnings,
        "diagnostics": diagnostics + coverage + [{
            "stage": "jd_reviewer_approval", "requirements": len(approved),
            "edited": edited,
        }],
    })
