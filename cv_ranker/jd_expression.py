"""Source-offset validated, supervisor-approved employer condition expression.

"Full" means no substantive JD words were silently left outside the
approved expression. A partial annotation cannot erase an unlisted sibling.
No occupation vocabulary or candidate outcome is encoded here.
"""
from __future__ import annotations

import re
from .schemas import JDConditionNode, ValidatedRequirement


def validate_expression(node: JDConditionNode, jd: str) -> None:
    """Reject invented spans, overlap, repeated spans and hidden JD obligations.

    Connectives and punctuation may remain outside source leaves. Articles,
    qualifiers, action/object words and quantitative restrictions may not.
    """
    leaves: list[JDConditionNode] = []
    def walk(branch: JDConditionNode) -> None:
        if branch.op == "leaf":
            if branch.start is None or branch.end is None or branch.start >= branch.end:
                raise ValueError('Approved JD leaf requires valid original source offsets')
            if jd[branch.start:branch.end] != branch.text:
                raise ValueError("Approved JD leaf must match exact original source offsets")
            leaves.append(branch)
        else:
            for child in branch.children:
                walk(child)
    walk(node)
    used = [False] * len(jd)
    for leaf in leaves:
        if leaf.start is None or leaf.end is None:
            raise ValueError('Approved JD expression has a missing leaf source range')
        for i in range(leaf.start, leaf.end):
            if used[i]:
                raise ValueError("Approved JD expression contains overlapping or repeated source spans")
            used[i] = True
    missing = ''.join(' ' if used[i] else c for i, c in enumerate(jd))
    # These are logical connectives, not occupational semantic heuristics.
    missing = re.sub(r"\b(?:and|or)\b", " ", missing, flags=re.I)
    if re.search(r"\w", missing):
        raise ValueError("Approved expression omits original JD condition text; review every remaining obligation")


def evaluate_expression(node: JDConditionNode,
                        leaf_states: dict[tuple[int,int], str]) -> str:
    """Evaluate evidence statuses in a three-valued Boolean logic.

    States: supported, missing, uncertain. Missing on an UNUSED OR branch
    cannot invalidate a supported alternative; an uncertain mandatory sibling
    cannot become a positive.
    """
    if node.op == "leaf":
        return leaf_states.get((node.start, node.end), "uncertain")
    statuses = [evaluate_expression(c, leaf_states) for c in node.children]
    if node.op == "all_of":
        return ("missing" if "missing" in statuses else
                "supported" if all(s == "supported" for s in statuses) else "uncertain")
    return ("supported" if "supported" in statuses else
            "missing" if all(s == "missing" for s in statuses) else "uncertain")
