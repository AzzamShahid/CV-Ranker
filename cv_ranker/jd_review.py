"""Human approval of source-grounded JD extraction, independent of CV scoring."""
from __future__ import annotations

from .requirement_typing import classify_requirement
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
            inferred = inferred.model_copy(update={
                "kind": kind,
                "minimum_years": inferred.minimum_years if kind == "experience" else None,
                "degree_level": inferred.degree_level if kind == "education" else None,
                "field_of_study": inferred.field_of_study if kind == "education" else None,
                "origin": "manual_review_pending", "requires_review": True,
            })
        requirement = base.model_copy(update={"constraint": RequirementConstraint.model_validate(inferred)})
        approved.append(requirement)
        if old != requirement:
            edited = True
    return draft.model_copy(update={
        "requirements": approved, "approved": True,
        "edited": edited,
        "diagnostics": list(draft.diagnostics) + [{
            "stage": "jd_reviewer_approval", "requirements": len(approved),
            "edited": edited,
        }],
    })
