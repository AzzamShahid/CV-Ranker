"""Streamlit interface for evidence-grounded candidate assessments.

UI is presentation-only: no additional candidate eligibility or ranking rules.
"""
from __future__ import annotations

import json
import hashlib
import tempfile
import csv
from html import escape
from copy import deepcopy
import io
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from queue import Empty, SimpleQueue

import streamlit as st

from cv_ranker import CVRanker, Settings
from cv_ranker.build_info import (ASSESSMENT_PROTOCOL, ASSESSMENT_PROTOCOL_VERSION,
                                  BUILD_ID, UI_RELEASE_VERSION)
from cv_ranker.config import default_ui_provider
from cv_ranker.documents import DocumentError, extract_text
from cv_ranker.runtime_check import assert_runtime_current
from cv_ranker.schemas import CandidateResult, JDReviewDraft, RankingReport
from cv_ranker.weighted_scoring import (
    ScoreWeights, allocation_bucket, even_requirement_shares,
    rebalance_requirement_share, criterion_bucket_counts, requirement_bucket,
    weighted_candidate, weighted_leaderboard,
)
from cv_ranker.report_bundle import complete_results_zip
from cv_ranker.ranking_reasoning import candidate_reasoning, comparative_reasoning
from cv_ranker.jd_review import approve_jd_rows, editable_jd_rows
from cv_ranker.resume import assessment_context_key, candidate_resume_keys
from cv_ranker.segments import segment_resume
from cv_ranker.text_utils import phrase_present, requirement_options
from cv_ranker.ui.evidence_inspection import literal_mentions, resume_segments, segment_ledger
from cv_ranker.ui.final_decisions import reconcile_candidate
from cv_ranker.ui.unified_decisions import reconcile_unified_candidate
from cv_ranker.ui.semantic_workflow import (
    semantic_candidate_rows, semantic_summary,
)
from cv_ranker.ui_support import (
    candidate_assessment_rows,
    final_leaderboard_rows,
    highlighted_source_html,
    report_json_bytes,
    safe_upload_name,
    save_uploaded_bytes,
)

ROOT = Path(__file__).resolve().parents[2]
MAX_RESUMES = 25
MAX_FILE_BYTES = 10 * 1024 * 1024
SUPPORTED_UPLOAD_TYPES = ["pdf", "docx", "txt", "md"]
SEMANTIC_CACHE = ROOT / "outputs" / "ui_semantic_cache.db"
# The worker only runs the pure assessment core. Streamlit state and widgets
# must be accessed exclusively by the UI thread when a result is published.
_RECOVERY_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="cvr-recovery")
_MAX_RATE_LIMITED_NO_PROGRESS = 3
_MAX_OTHER_NO_PROGRESS = 2
_SNAPSHOT_KEYS = (
    "cv_ranking_report", "cv_run_label", "cv_run_requirement_limit",
    "cv_run_provider", "cv_source_ledgers", "cv_source_ledger_errors",
    "cv_unified_metrics", "cv_request_metrics", "cv_final_results",
    "cv_resume_cache",
)


def _progress_caption(queue_key: str, started_key: str) -> str:
    """Read thread-safe progress without allowing workers to touch Streamlit."""
    mailbox = st.session_state.get(queue_key)
    latest = "Preparing resume evidence"
    if isinstance(mailbox, SimpleQueue):
        while True:
            try:
                latest = mailbox.get_nowait()
            except Empty:
                break
        if latest != "Preparing resume evidence":
            st.session_state[queue_key + "_latest"] = latest
    latest = st.session_state.get(queue_key + "_latest", latest)
    started = st.session_state.get(started_key)
    elapsed = max(0, int(time.monotonic() - started)) if isinstance(started, (int, float)) else 0
    return f"{latest} · {elapsed}s elapsed"


def _styles():
    st.markdown("""
    <style>
    :root {--cv-navy:#18334c;--cv-blue:#3265a8;--cv-teal:#16877d;
           --cv-ink:var(--text-color);--cv-line:rgba(113,135,158,.23);
           --cv-muted:var(--text-color);}
    .block-container {max-width:1350px;padding-top:1.15rem;padding-bottom:2.8rem;}
    [data-testid="stAppViewContainer"] {background:
      radial-gradient(circle at 96% 0%,rgba(38,122,168,.065),transparent 30%),
      radial-gradient(circle at 0% 42%,rgba(22,135,125,.035),transparent 34%),
      var(--background-color);}
    .cv-hero {position:relative;overflow:hidden;display:flex;align-items:center;
      justify-content:space-between;gap:2rem;margin:.15rem 0 1.5rem;
      padding:1.6rem 1.85rem;border-radius:21px;color:#f8fbff;
      background:linear-gradient(112deg,#112c46 0%,#1b4c68 61%,#127b76 100%);
      border:1px solid rgba(255,255,255,.13);box-shadow:0 12px 32px rgba(14,42,66,.16);}
    .cv-hero:after {content:"";position:absolute;width:17rem;height:17rem;
      top:-10rem;right:9%;border-radius:50%;border:2.5rem solid rgba(255,255,255,.05);
      pointer-events:none;}
    .cv-hero-title {font-size:clamp(1.55rem,3vw,2.15rem);font-weight:790;
      letter-spacing:-.035em;line-height:1.12;margin:.32rem 0 .55rem;}
    .cv-hero-description {color:rgba(240,250,255,.86);font-size:.94rem;
      line-height:1.55;margin:0;max-width:47rem;}
    .cv-hero-badge {font-size:.7rem;letter-spacing:.12em;text-transform:uppercase;
      font-weight:800;color:#b7f1e6;}
    .cv-hero-mark {position:relative;z-index:1;display:grid;place-items:center;
      flex-shrink:0;width:4.25rem;height:4.25rem;border-radius:16px;
      background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.2);
      font-size:1.95rem;font-weight:700;color:#f3fffd;}
    .cv-section {display:flex;align-items:flex-start;gap:.8rem;
      margin:1.35rem 0 .72rem;padding-bottom:.65rem;
      border-bottom:1px solid var(--cv-line);}
    .cv-section-line {width:4px;min-height:2.65rem;border-radius:8px;
      background:linear-gradient(180deg,#2374b8,#16a394);flex-shrink:0;margin-top:.12rem;}
    .cv-section-eyebrow,.cv-card-eyebrow {font-size:.68rem;letter-spacing:.11em;
      text-transform:uppercase;font-weight:800;color:#16877d;margin:0 0 .15rem;}
    .cv-section-heading {font-size:1.16rem;font-weight:770;letter-spacing:-.012em;
      color:var(--cv-ink);margin:0 0 .2rem;line-height:1.32;}
    .cv-section-subtitle {font-size:.83rem;opacity:.72;line-height:1.4;margin:0;color:var(--cv-ink);}
    .cv-insight {position:relative;overflow:hidden;margin:.45rem 0 1rem;
      border:1px solid var(--cv-line);border-left:4px solid #238c82;
      border-radius:16px;background:var(--secondary-background-color);
      box-shadow:0 5px 21px rgba(24,51,76,.055);padding:1.1rem 1.3rem 1.05rem;}
    .cv-insight.is-blue {border-left-color:#3877b7;}
    .cv-insight.is-amber {border-left-color:#bc8b37;}
    .cv-insight.is-slate {border-left-color:#8394a5;}
    .cv-insight-top {display:flex;flex-wrap:wrap;align-items:center;
      justify-content:space-between;gap:.4rem;margin-bottom:.38rem;}
    .cv-insight-label {font-size:.71rem;text-transform:uppercase;letter-spacing:.075em;
      color:#218b81;font-weight:800;}
    .cv-insight.is-blue .cv-insight-label {color:#3979b9;}
    .cv-insight.is-amber .cv-insight-label {color:#aa782f;}
    .cv-insight.is-slate .cv-insight-label {color:#748697;}
    .cv-insight-tag {font-size:.71rem;font-weight:700;padding:.23rem .55rem;
      border-radius:99px;background:rgba(35,140,130,.085);color:var(--cv-ink);
      border:1px solid var(--cv-line);}
    .cv-insight-heading {margin:0 0 .35rem;font-size:.99rem;font-weight:760;
      line-height:1.45;color:var(--cv-ink);overflow-wrap:anywhere;}
    .cv-insight-body {margin:0;color:var(--cv-ink);opacity:.88;
      font-size:.91rem;line-height:1.64;overflow-wrap:anywhere;}
    .cv-rank-row {display:flex;align-items:flex-start;gap:1rem;
      padding:1rem 1.15rem;margin:.55rem 0;border:1px solid var(--cv-line);
      border-radius:14px;background:var(--secondary-background-color);
      box-shadow:0 3px 12px rgba(24,51,76,.035);}
    .cv-rank-row.is-top {border-left:4px solid #16877d;}
    .cv-rank-row.is-pending {border-left:4px solid #bc8b37;}
    .cv-rank-position {display:flex;align-items:center;justify-content:center;
      flex:0 0 3rem;min-height:3rem;border-radius:11px;
      background:rgba(48,107,166,.09);color:var(--cv-ink);font-weight:800;
      font-size:.91rem;white-space:nowrap;}
    .cv-rank-row.is-top .cv-rank-position {background:rgba(22,135,125,.12);}
    .cv-rank-row.is-pending .cv-rank-position {background:rgba(188,139,55,.12);}
    .cv-rank-content {flex:1;min-width:0;}
    .cv-rank-topline {display:flex;gap:.6rem;justify-content:space-between;
      align-items:baseline;flex-wrap:wrap;margin-bottom:.33rem;}
    .cv-rank-name {font-size:1rem;font-weight:780;color:var(--cv-ink);
      letter-spacing:-.01em;overflow-wrap:anywhere;}
    .cv-rank-score {font-size:.82rem;font-weight:800;padding:.22rem .65rem;
      border-radius:100px;background:rgba(30,139,130,.095);
      border:1px solid var(--cv-line);color:var(--cv-ink);white-space:nowrap;}
    .cv-rank-reason {font-size:.87rem;color:var(--cv-ink);opacity:.86;
      line-height:1.57;overflow-wrap:anywhere;}
    .cv-mini-title {font-size:.79rem;font-weight:800;letter-spacing:.045em;
      text-transform:uppercase;color:var(--cv-ink);margin:.3rem 0 .7rem;}
    .cv-mini-item {border-left:2px solid #2d9c8e;padding:.5rem .7rem;
      margin:.38rem 0;border-radius:0 9px 9px 0;background:rgba(29,142,128,.055);}
    .cv-mini-item.is-gap {border-left-color:#c89a49;background:rgba(192,144,53,.06);}
    .cv-mini-name {font-weight:710;color:var(--cv-ink);font-size:.9rem;line-height:1.4;}
    .cv-mini-points {font-size:.76rem;color:var(--cv-ink);opacity:.72;margin:.18rem 0;}
    .cv-mini-description {font-size:.8rem;color:var(--cv-ink);opacity:.8;
      line-height:1.47;margin-top:.25rem;overflow-wrap:anywhere;}
    div[data-testid="stMetric"] {border:1px solid var(--cv-line);
      border-top:3px solid rgba(30,139,130,.65);border-radius:13px;
      padding:.75rem 1rem;background:var(--secondary-background-color);
      box-shadow:0 4px 16px rgba(24,51,76,.045);min-height:6.2rem;}
    div[data-testid="stMetricLabel"] {font-weight:650;letter-spacing:.01em;}
    div[data-testid="stMetricValue"] {font-size:1.58rem;font-weight:790;
      letter-spacing:-.03em;}
    div[data-testid="stTabs"] [data-baseweb="tab-list"] {gap:.4rem;
      border-bottom:1px solid var(--cv-line);padding-bottom:.3rem;}
    div[data-testid="stTabs"] button[role="tab"] {border-radius:11px 11px 0 0;
      font-weight:700;padding:.7rem 1rem;transition:background .18s ease;}
    div[data-testid="stTabs"] button[role="tab"][aria-selected="true"]
      {background:rgba(30,139,130,.075);}
    [data-testid="stExpander"] {border:1px solid var(--cv-line);
      border-radius:13px;overflow:hidden;background:var(--secondary-background-color);}
    [data-testid="stExpander"] summary {font-weight:680;}
    [data-testid="stDataFrame"] {border:1px solid var(--cv-line);
      border-radius:13px;overflow:hidden;}
    [data-testid="stFileUploader"] {border-radius:13px;}
    [data-testid="stButton"] button[kind="primary"],
    [data-testid="stDownloadButton"] button[kind="primary"] {
      border-radius:10px;font-weight:750;box-shadow:0 3px 12px rgba(32,104,155,.12);}
    .cv-kicker {font-size:.72rem;letter-spacing:.12em;text-transform:uppercase;
      color:#16877d;font-weight:800;}
    .cv-muted {opacity:.75;font-size:.92rem;}
    .cv-source {white-space:pre-wrap;overflow-wrap:anywhere;padding:.95rem 1.05rem;
      border:1px solid var(--cv-line);border-left:3px solid #4482ab;
      border-radius:11px;margin:.45rem 0 .9rem;background:var(--secondary-background-color);
      font-size:.9rem;line-height:1.55;}
    @media(max-width:700px) {
      .block-container {padding-top:.6rem;}
      .cv-hero {padding:1.2rem;gap:1rem;border-radius:15px;}
      .cv-hero-mark {display:none;}
      .cv-insight {padding:.85rem .95rem;}
      .cv-section-heading {font-size:1.04rem;}
      .cv-rank-row {padding:.82rem .9rem;gap:.7rem;}
      .cv-rank-position {flex-basis:2.3rem;min-height:2.3rem;font-size:.8rem;}
    }
    </style>""", unsafe_allow_html=True)


def _section_title(title: str, subtitle: str, *, eyebrow: str = "Assessment insight") -> None:
    """A compact, consistent section heading with no data-dependent HTML."""
    st.markdown(
        '<div class="cv-section"><span class="cv-section-line"></span><div>'
        f'<div class="cv-section-eyebrow">{escape(eyebrow)}</div>'
        f'<h3 class="cv-section-heading">{escape(title)}</h3>'
        f'<p class="cv-section-subtitle">{escape(subtitle)}</p>'
        '</div></div>', unsafe_allow_html=True,
    )


def _insight_card(title: str, body: str, *, label: str, tag: str = "",
                  tone: str = "teal") -> None:
    """Source-grounded summary card; user CV/JD text is always HTML-escaped."""
    safe_tone = tone if tone in {"blue", "amber", "slate"} else "teal"
    pill = f'<span class="cv-insight-tag">{escape(tag)}</span>' if tag else ''
    st.markdown(
        f'<div class="cv-insight is-{safe_tone}">'
        f'<div class="cv-insight-top"><span class="cv-insight-label">{escape(label)}</span>{pill}</div>'
        f'<div class="cv-insight-heading">{escape(title)}</div>'
        f'<p class="cv-insight-body">{escape(body)}</p></div>',
        unsafe_allow_html=True,
    )


def _evidence_tile(item: dict, *, gap: bool = False) -> None:
    """Readable requirement evidence with the same point values as scoring."""
    points = item.get("possible_points") if gap else item.get("earned_points")
    label = (_scored_points_text(points) + " unearned" if gap and points is not None
             else _scored_points_text(points, prefix="+" if not gap else ""))
    style = " is-gap" if gap else ""
    st.markdown(
        f'<div class="cv-mini-item{style}">'
        f'<div class="cv-mini-name">{escape(str(item["requirement"]))}</div>'
        f'<div class="cv-mini-points">{escape(label)}</div>'
        f'<div class="cv-mini-description">{escape(str(item["why"]))}</div>'
        '</div>', unsafe_allow_html=True,
    )


def _rank_explanation_row(explanation: dict) -> None:
    """One easily scanned candidate placement, without duplicating audit blocks."""
    rank = explanation.get("rank")
    score = explanation.get("weighted_score")
    marker = f"#{rank}" if rank is not None else "—"
    score_label = f"{score:.2f}%" if score is not None else "Not ranked"
    reason = explanation.get("placement_reason") or explanation.get("summary") or ""
    style = " is-top" if rank == 1 else " is-pending" if rank is None else ""
    st.markdown(
        f'<div class="cv-rank-row{style}">'
        f'<div class="cv-rank-position">{escape(marker)}</div>'
        f'<div class="cv-rank-content"><div class="cv-rank-topline">'
        f'<span class="cv-rank-name">{escape(str(explanation["candidate"]))}</span>'
        f'<span class="cv-rank-score">{escape(score_label)}</span></div>'
        f'<div class="cv-rank-reason">{escape(str(reason))}</div></div></div>',
        unsafe_allow_html=True,
    )


def _sync_weight(key: str, source: str) -> None:
    other = "number" if source == "slider" else "slider"
    st.session_state[f"cv_weight_{other}_{key}"] = st.session_state[f"cv_weight_{source}_{key}"]


def _weight_controls(label: str, key: str, default: int) -> int:
    slider_key = f"cv_weight_slider_{key}"
    number_key = f"cv_weight_number_{key}"
    if slider_key not in st.session_state:
        st.session_state[slider_key] = default
    if number_key not in st.session_state:
        st.session_state[number_key] = default
    left, right = st.columns([2, 1], gap="small")
    with left:
        st.slider(label, min_value=0, max_value=100, key=slider_key,
                  on_change=_sync_weight, args=(key, "slider"))
    with right:
        st.number_input(f"{label} %", min_value=0, max_value=100, step=1,
                        key=number_key, on_change=_sync_weight,
                        args=(key, "number"), label_visibility="collapsed")
    return int(st.session_state[slider_key])


def _scored_points_text(points: float | None, *, prefix: str = "") -> str:
    """Unverified candidates have no attributable weighted points.

    Do not format ``None`` as a float or imply that a partial assessment
    earned/forfeited points while the candidate's overall rank is withheld.
    """
    return (f"{prefix}{points:.2f} points" if points is not None
            else "points withheld · assessment incomplete")


def _allocation_key(requirements) -> str:
    """Bind edited shares to the exact frozen JD, not current CVs or ranking."""
    frozen = [req.model_dump(mode="json") for req in requirements]
    return hashlib.sha256(json.dumps(frozen, sort_keys=True).encode("utf-8")).hexdigest()


def _allocation_for(requirements) -> dict[str, float]:
    fingerprint = _allocation_key(requirements)
    saved = st.session_state.get("cv_requirement_allocations", {}).get(fingerprint)
    if not isinstance(saved, dict) or set(saved) != {r.requirement_id for r in requirements}:
        saved = even_requirement_shares(list(requirements))
        st.session_state.setdefault("cv_requirement_allocations", {})[fingerprint] = saved
    return dict(saved)


def _change_requirement_share(requirements, fingerprint: str, changed_id: str) -> None:
    saved = _allocation_for(requirements)
    widget_key = f"cv_item_share_{fingerprint[:12]}_{changed_id}"
    try:
        updated = rebalance_requirement_share(
            list(requirements), saved, changed_id, st.session_state[widget_key])
    except (KeyError, ValueError) as exc:
        st.session_state["cv_weight_allocation_error"] = str(exc)
        st.session_state[widget_key] = saved[changed_id]
        return
    st.session_state.pop("cv_weight_allocation_error", None)
    st.session_state["cv_requirement_allocations"][fingerprint] = updated
    for identifier, value in updated.items():
        st.session_state[f"cv_item_share_{fingerprint[:12]}_{identifier}"] = value


def _current_weights(report: RankingReport | None = None) -> ScoreWeights:
    shares = (_allocation_for(report.requirements) if report is not None else {})
    return ScoreWeights(
        experience=int(st.session_state.get("cv_weight_slider_experience", 10)),
        education=int(st.session_state.get("cv_weight_slider_education", 10)),
        jd=int(st.session_state.get("cv_weight_slider_jd", 80)),
        split_jd=bool(st.session_state.get("cv_weight_split", False)),
        required_share=int(st.session_state.get("cv_weight_slider_required", 80)),
        requirement_shares=tuple(sorted(shares.items())),
    )


def _fill_weight_remainder() -> None:
    remainder = 100 - int(st.session_state.get("cv_weight_slider_experience", 10)) - int(
        st.session_state.get("cv_weight_slider_education", 10))
    if 0 <= remainder <= 100:
        st.session_state["cv_weight_slider_jd"] = remainder
        st.session_state["cv_weight_number_jd"] = remainder


def _open_page(page: str) -> None:
    st.session_state["cv_active_page"] = page


def _toggle_jd_split() -> None:
    st.session_state["cv_weight_split"] = not st.session_state.get("cv_weight_split", False)


def _clear_results() -> None:
    """Clear the active run without changing uploaded source inputs or weights."""
    future = st.session_state.get("cv_manual_assessment_future")
    if isinstance(future, Future):
        future.cancel()  # Queued work is cancelable; active HTTP calls are not.
    for key in (
        "cv_ranking_report", "cv_run_label", "cv_run_provider",
        "cv_run_requirement_limit", "cv_semantic_report", "cv_semantic_error",
        "cv_semantic_retrieval", "cv_final_results", "cv_source_ledgers",
        "cv_source_ledger_errors", "cv_unified_metrics", "cv_request_metrics",
        "cv_resume_cache", "cv_jd_review_pending", "cv_auto_resume_state",
        "cv_auto_resume_future", "cv_provider_hard_stop",
        "cv_manual_assessment_future", "cv_manual_assessment_state",
    ):
        st.session_state.pop(key, None)


def _weightage_panel(requirements) -> bool:
    """After JD approval, edit three category totals and every frozen JD share."""
    initial = (
        int(st.session_state.get("cv_weight_slider_experience", 10)),
        int(st.session_state.get("cv_weight_slider_education", 10)),
        int(st.session_state.get("cv_weight_slider_jd", 80)),
    )
    _section_title("Step 4 · Category weightage",
                   "Set the overall scoring priorities for the approved job description.",
                   eyebrow="Review & prioritize")
    with st.expander(
        f"Category weights — {initial[0]}% / {initial[1]}% / {initial[2]}%",
        expanded=True,
    ):
        experience = _weight_controls("Experience", "experience", 10)
        education = _weight_controls("Education", "education", 10)
        jd = _weight_controls("JD requirements", "jd", 80)
        allocated = experience + education + jd
        st.progress(min(allocated, 100), text=f"Allocated {allocated} / 100 marks")
        if allocated != 100:
            difference = 100 - allocated
            st.error(f"{'Allocate' if difference > 0 else 'Remove'} {abs(difference)} marks to reach exactly 100.")
        if 0 <= 100 - experience - education <= 100:
            st.button("Fill remainder into JD requirements", on_click=_fill_weight_remainder,
                      key="cv_weight_fill_remainder")
        st.caption("Category weights apply only when that category exists in the approved JD. "
                   "Empty categories are excluded and the remaining weights are renormalized.")
    fingerprint = _allocation_key(requirements)
    shares = _allocation_for(requirements)
    by_category = {category: [] for category in ("experience", "education", "jd")}
    for requirement in requirements:
        by_category[allocation_bucket(requirement)].append(requirement)
    category_weights = {"experience": experience, "education": education, "jd": jd}
    active_weight = sum(category_weights[key] for key, rows in by_category.items() if rows)
    _section_title("Step 5 · Edit individual JD allocations",
                   "Give individual requirements more or less influence within their category.",
                   eyebrow="Review & prioritize")
    with st.expander("Individual requirement allocations (within each category)", expanded=True):
        st.caption("All percentages below are shares of their own category, not additional overall points. "
                   "Changing one share automatically rebalances only the other items in that same category. "
                   "Required and Preferred remain together in ONE JD allocation pool.")
        for category, entries in by_category.items():
            if not entries:
                continue
            st.markdown(f"**{category.title()} · {len(entries)} requirement(s) · 100% of this category**")
            for req in entries:
                left, right = st.columns([4, 1])
                with left:
                    label = f"{req.requirement_id} · {req.name}"
                    if category == "jd":
                        label += f" · {req.priority.title()}"
                    st.caption(label)
                    if active_weight:
                        potential = 100.0 * category_weights[category] / active_weight * shares[req.requirement_id] / 100
                        st.caption(f"Possible overall score: {potential:.2f} / 100 points")
                with right:
                    identifier = f"cv_item_share_{fingerprint[:12]}_{req.requirement_id}"
                    if identifier not in st.session_state:
                        st.session_state[identifier] = shares[req.requirement_id]
                    st.number_input(
                        f"{req.requirement_id} share of {category} (%)",
                        min_value=0.0, max_value=100.0, step=0.01, format="%.2f",
                        key=identifier, label_visibility="collapsed", disabled=len(entries) == 1,
                        on_change=_change_requirement_share,
                        args=(requirements, fingerprint, req.requirement_id),
                    )
        if st.session_state.get("cv_weight_allocation_error"):
            st.error(st.session_state["cv_weight_allocation_error"])
        if st.button("Reset all individual shares to equal", key="cv_reset_jd_shares"):
            even = even_requirement_shares(list(requirements))
            st.session_state["cv_requirement_allocations"][fingerprint] = even
            for identifier, value in even.items():
                st.session_state[f"cv_item_share_{fingerprint[:12]}_{identifier}"] = value
            st.session_state.pop("cv_weight_allocation_error", None)
            st.rerun()
    return allocated == 100 and not st.session_state.get("cv_weight_allocation_error")


def _get_report():
    data = st.session_state.get("cv_ranking_report")
    if data is None:
        return None
    try:
        return RankingReport.model_validate(data)
    except Exception:
        st.session_state.pop("cv_ranking_report", None)
        return None


def _archive_current_run(state) -> None:
    """Keep a few reports recoverable inside this Streamlit session only.

    Nothing is written to the filesystem, so private CV passages never gain a
    new persistence channel. For retention after the browser session ends,
    download the export deliberately.
    """
    if not state.get("cv_ranking_report"):
        return
    snapshot = {key: deepcopy(state[key]) for key in _SNAPSHOT_KEYS if key in state}
    history = list(state.get("cv_run_history", []))
    history.insert(0, snapshot)
    state["cv_run_history"] = history[:3]


def _restore_archived_run(state, index: int) -> None:
    history = list(state.get("cv_run_history", []))
    if not isinstance(index, int) or index < 0 or index >= len(history):
        raise ValueError("Previous report is no longer in this session")
    selected = history.pop(index)
    _archive_current_run(state)
    # The current report is now at position zero; keep the remaining prior
    # snapshots behind it, without duplicating the selected restored run.
    state["cv_run_history"] = [state["cv_run_history"][0]] + history[:2]
    for key in _SNAPSHOT_KEYS:
        state.pop(key, None)
    state.pop("cv_auto_resume_state", None)
    state.pop("cv_auto_resume_future", None)
    pending_job = state.pop("cv_manual_assessment_future", None)
    if isinstance(pending_job, Future):
        pending_job.cancel()
    state.pop("cv_manual_assessment_state", None)
    state.pop("cv_provider_hard_stop", None)
    for key, value in selected.items():
        state[key] = deepcopy(value)
    for key in ("cv_candidate_selector", "cv_candidate_status",
                "cv_candidate_priority", "cv_candidate_group", "cv_source_candidate",
                "cv_segment_search", "cv_segment_section"):
        state.pop(key, None)


def _save_report(report: RankingReport, label: str, config: Settings, use_llm: bool, is_upload: bool) -> None:
    _archive_current_run(st.session_state)
    if is_upload:
        # Don't leak temporary paths in downloadable reports after temporary files are destroyed.
        cleaned = []
        for candidate in report.candidates:
            src = Path(candidate.candidate_source) if candidate.candidate_source else None
            slot = src.parent.name if src else "unknown"
            cleaned.append(candidate.model_copy(update={
                "candidate_source": f"uploaded://{slot}/{candidate.candidate_name}"
            }))
        report = report.model_copy(update={
            "job_description_source": "User-supplied job description (temporary)",
            "candidates": cleaned,
        })
    st.session_state["cv_ranking_report"] = report.model_dump()
    # Do not retain a positional candidate selector when a new report is loaded.
    st.session_state.pop("cv_candidate_selector", None)
    st.session_state.pop("cv_candidate_status", None)
    st.session_state.pop("cv_candidate_priority", None)
    st.session_state.pop("cv_candidate_group", None)
    st.session_state.pop("cv_source_candidate", None)
    st.session_state.pop("cv_segment_search", None)
    st.session_state.pop("cv_segment_section", None)
    st.session_state["cv_run_label"] = label
    st.session_state["cv_run_requirement_limit"] = config.max_requirements
    st.session_state["cv_run_provider"] = f"{config.llm_provider} · {config.model_name}" if use_llm else "offline exact fallback"
    # A previous experimental file must never remain attached after a new run.
    st.session_state.pop("cv_semantic_report", None)
    st.session_state.pop("cv_semantic_error", None)
    st.session_state.pop("cv_semantic_retrieval", None)
    st.session_state.pop("cv_final_results", None)


def _rank(
    jd: Path, cv_paths: list[Path], settings: Settings, use_llm: bool,
    label: str, uploaded: bool = False, semantic_enabled: bool = False,
    resume: bool = False, approved_jd: JDReviewDraft | None = None,
):
    artifacts = _rank_core(
        jd, cv_paths, settings, use_llm, uploaded=uploaded, resume=resume,
        approved_jd=approved_jd,
        previous=st.session_state.get("cv_resume_cache") if resume else None,
    )
    _publish_rank_artifacts(artifacts, settings, use_llm, label, uploaded)
    return artifacts["report"]


def _rank_core(
    jd: Path, cv_paths: list[Path], settings: Settings, use_llm: bool, *,
    uploaded: bool, resume: bool, approved_jd: JDReviewDraft | None,
    previous: dict | None, progress_callback=None,
) -> dict:
    """Pure assessment; safe to execute off the Streamlit script thread."""
    # V4.8: the approved local retrieval feeds the FIRST LLM assessment.
    # There is no second shadow/reconciliation LLM pass.
    base_key = assessment_context_key(
        settings, jd_bytes=jd.read_bytes(),
        approved_aliases_bytes=(Path(settings.approved_aliases_path).read_bytes()
                                if settings.approved_aliases_path else b""),
        eligibility_policy_bytes=(Path(settings.eligibility_policy_path).read_bytes()
                                  if settings.eligibility_policy_path else b""),
        use_llm=use_llm,
    )
    context_key = _approval_context_key(base_key, approved_jd)
    if resume and (not isinstance(previous, dict)
                   or previous.get("context_key") != context_key):
        raise ValueError("Cannot resume: JD, provider, model, settings or HR policies changed. "
                         "Use Analyze and rank for a fresh assessment.")
    previous_report = (RankingReport.model_validate(previous["report"])
                       if previous else None)
    if resume and use_llm and previous_report.jd_validation_mode != "llm_validated":
        raise ValueError("Cannot reuse a JD extracted through structural fallback. "
                         "Run a fresh LLM assessment after provider recovery.")
    previous_candidates = ({key: CandidateResult.model_validate(candidate)
                            for key, candidate in previous.get("candidates", {}).items()}
                           if previous else None)
    previous_attempts = int((previous or {}).get("assessment_http_attempts_total", 0))
    budget_settings = settings
    if use_llm and settings.llm_provider == "openrouter":
        remaining = settings.openrouter_max_requests_per_assessment - previous_attempts
        if remaining <= 0:
            raise ValueError(
                "Cloud assessment request budget exhausted for this JD/CV checkpoint. "
                "Completed and partial results remain saved; increase "
                "OPENROUTER_MAX_REQUESTS_PER_ASSESSMENT deliberately before resuming.")
        run_limit = settings.openrouter_max_requests_per_run
        budget_settings = replace(settings, openrouter_max_requests_per_run=(
            min(remaining, run_limit) if run_limit > 0 else remaining))
    ranker = CVRanker(settings=budget_settings, use_llm=use_llm, unified=use_llm,
                      embedding_cache_path=SEMANTIC_CACHE,
                      **({"progress_callback": progress_callback}
                         if callable(progress_callback) else {}))
    run_kwargs = {"resume_report": previous_report,
                  "resume_candidates": previous_candidates}
    if approved_jd is not None:
        run_kwargs["approved_jd"] = approved_jd
    report = ranker.run(jd, cv_paths, **run_kwargs)
    # Match assessed rows by the actual temporary source path, not their
    # leaderboard order (which changes when scores are assigned).
    names_to_keys = dict(zip(
        (str(path) for path in cv_paths),
        candidate_resume_keys([(path.name, path.read_bytes()) for path in cv_paths])))
    resume_entries = {}
    for candidate in report.candidates:
        key = names_to_keys.get(candidate.candidate_source)
        if key:
            source = Path(candidate.candidate_source)
            safe_source = (f"uploaded://{source.parent.name}/{candidate.candidate_name}"
                           if uploaded else candidate.candidate_source)
            resume_entries[key] = candidate.model_copy(update={
                "candidate_source": safe_source, "rank": None,
            }).model_dump()
    # Uploaded CVs reside in a TemporaryDirectory. Save the exact parsed
    # segments before it closes so all original evidence can be inspected.
    ledgers = {}
    ledger_errors = {}
    for index, candidate in enumerate(report.candidates):
        try:
            sources = ranker.source_ledgers.get(candidate.candidate_source)
            if sources is None:
                sources = segment_resume(extract_text(candidate.candidate_source))
            ledgers[str(index)] = segment_ledger(sources)
        except (DocumentError, OSError, ValueError) as exc:
            ledger_errors[str(index)] = f"Could not retain source segments: {exc}"
    # Reconcile BEFORE publishing anything to session state. If detail Found
    # counts and scored Found counts disagree, fail the publication contract;
    # never show a persuasive but internally contradictory supervisor report.
    final_results = {}
    for index in range(len(report.candidates)):
        if use_llm:
            final_results[str(index)] = reconcile_unified_candidate(
                report, index, ledgers.get(str(index), []))
        else:
            final_results[str(index)] = reconcile_candidate(
                report, index, ledgers.get(str(index), []), llm=None)
        candidate = report.candidates[index]
        final = final_results[str(index)]
        if use_llm and candidate.primary_score is not None and (
                candidate.matched_required != final["Required matched"] or
                candidate.total_required != final["Required total"] or
                candidate.matched_preferred != final["Preferred matched"] or
                candidate.total_preferred != final["Preferred total"]):
            raise RuntimeError(
                "Scoring/evidence reconciliation failed for candidate "
                f"{index + 1}; report publication stopped. Inspect source validation diagnostics."
            )
    unified_metrics = {
        str(index): ranker.unified_metrics.get(candidate.candidate_source, {})
        for index, candidate in enumerate(report.candidates)
    }
    provider_failure = str(getattr(ranker.llm, "disabled_reason", "") or "")
    provider_hard_stop = bool(
        settings.llm_provider == "openrouter" and any(
            f"OpenRouter HTTP {status}" in provider_failure
            for status in (401, 402, 403, 404)))
    current_attempts = int(ranker.request_metrics.get("actual_model_request_attempts", 0))
    cumulative_attempts = previous_attempts + current_attempts
    ranker.request_metrics["assessment_http_attempts_cumulative"] = cumulative_attempts
    if use_llm and settings.llm_provider == "openrouter":
        ranker.request_metrics["assessment_http_attempt_budget"] = (
            settings.openrouter_max_requests_per_assessment)
        ranker.request_metrics["assessment_http_attempts_remaining"] = max(
            0, settings.openrouter_max_requests_per_assessment - cumulative_attempts)
    resume_cache = {
        "context_key": context_key,
        "report": report.model_dump(),
        "candidates": resume_entries,
        "assessment_http_attempts_total": cumulative_attempts,
    }
    # Do not let repeated clicking immediately burn the same provider quota.
    cooldown_seconds = 0.0
    if (settings.llm_provider == "openrouter" and ranker.llm is not None
            and "429" in str(getattr(ranker.llm, "disabled_reason", ""))):
        cooldown_seconds = max(60.0, settings.openrouter_retry_delay_seconds * 4,
                               float(getattr(ranker.llm, "last_retry_after_seconds", 0) or 0))
    return {
        "report": report, "ledgers": ledgers, "ledger_errors": ledger_errors,
        "unified_metrics": unified_metrics, "request_metrics": ranker.request_metrics,
        "provider_hard_stop": provider_hard_stop, "final_results": final_results,
        "resume_cache": resume_cache, "cooldown_seconds": cooldown_seconds,
    }


def _publish_rank_artifacts(artifacts: dict, settings: Settings, use_llm: bool,
                            label: str, uploaded: bool) -> None:
    """Only the Streamlit script thread may publish worker results."""
    _save_report(artifacts["report"], label, settings, use_llm, uploaded)
    for key, value in (
        ("cv_source_ledgers", artifacts["ledgers"]),
        ("cv_source_ledger_errors", artifacts["ledger_errors"]),
        ("cv_unified_metrics", artifacts["unified_metrics"]),
        ("cv_request_metrics", artifacts["request_metrics"]),
        ("cv_provider_hard_stop", artifacts["provider_hard_stop"]),
        ("cv_final_results", artifacts["final_results"]),
        ("cv_resume_cache", artifacts["resume_cache"]),
    ):
        st.session_state[key] = value
    if artifacts["cooldown_seconds"]:
        st.session_state["cv_provider_cooldown"] = {
            "provider": settings.llm_provider, "model": settings.model_name,
            "until": time.monotonic() + artifacts["cooldown_seconds"],
        }


def _sidebar() -> tuple[Settings | None, bool, bool]:
    with st.sidebar:
        st.markdown('<p class="cv-kicker">Assessment workspace</p>', unsafe_allow_html=True)
        st.markdown("### Configure screening")
        use_llm = st.toggle("AI-assisted assessment", value=True, help="Uses your configured local Ollama or OpenRouter LLM. Switch off for exact-only fallback.")
        default_provider = default_ui_provider()
        provider_names = {"Cloud (OpenRouter)": "openrouter", "Local (Ollama)": "ollama"}
        selected_provider = st.radio(
            "AI provider", list(provider_names),
            index=0 if default_provider == "openrouter" else 1,
            help="Select Cloud or Local here. Model names, URL and keys are configured only in .env.",
            key="cv_ui_provider",
        )
        try:
            configured = Settings(llm_provider=provider_names[selected_provider])
        except ValueError as exc:
            st.error(f"Configuration: {exc}")
            st.caption("Edit .env to configure this provider, or select the other provider above.")
            return None, use_llm, False
        st.caption(f"Model from `.env`: `{configured.model_name}`")
        st.markdown("**JD display**")
        st.session_state.setdefault("cv_weight_split", False)
        st.button(
            "Combine JD groups" if st.session_state["cv_weight_split"]
            else "Split JD into Required / Preferred",
            key="cv_weight_split_button", width="stretch", on_click=_toggle_jd_split,
        )
        if st.session_state["cv_weight_split"]:
            st.caption("Show Required and Preferred counts separately. "
                       "Their editable individual allocations still share one JD scoring pool.")
        with st.expander("Extraction limits & cloud recovery", expanded=False):
            yake_limit = st.slider(
                "YAKE candidate phrases limit", min_value=10, max_value=200,
                value=max(10, min(int(configured.yake_top_k), 200)), step=5,
                key="cv_yake_top_k",
                help="Maximum keyword/phrase suggestions extracted from the JD. "
                     "YAKE suggestions help discovery but do not automatically count as requirements.",
            )
            req_limit = st.slider("Frozen JD requirement processing limit", 5, 100, configured.max_requirements, 5,
                                  help="Guardrail only. The engine must not silently score truncated JDs.")
            st.checkbox(
                "Automatically resume unfinished cloud assessments",
                value=bool(use_llm and configured.llm_provider == "openrouter"),
                key="cv_auto_resume_enabled",
                disabled=not (use_llm and configured.llm_provider == "openrouter"),
                help="While connected, automatically retry incomplete cloud assessments after rate limits. "
                     "Additional requests may incur charges; authentication errors stop recovery.",
            )
        with st.expander("Employer policies · optional", expanded=False):
            st.file_uploader("Reviewer-approved JD equivalences (JSON)", type=["json"],
                             key="approved_aliases", help="Only use reviewer-approved JD-specific equivalent expressions.")
            st.file_uploader("Employer eligibility gates (JSON)", type=["json"],
                             key="eligibility_gates", help="Only use employer-approved eligibility requirements.")
            st.caption("These policies do not add weightage points and are not needed for normal screening.")
        with st.expander("Session controls", expanded=False):
            st.button("Clear current results", on_click=_clear_results,
                      key="cv_clear_active_results", width="stretch")
        st.caption("Cloud mode sends CV excerpts to OpenRouter.")
        st.caption(f"Interface V{UI_RELEASE_VERSION} · Assessment protocol v{ASSESSMENT_PROTOCOL_VERSION}")
        return Settings(
            llm_provider=configured.llm_provider,
            yake_top_k=yake_limit,
            max_requirements=req_limit,
            exact_initialism_guard=True,
            llm_type_review=configured.llm_type_review,
        ), use_llm, use_llm


def _uploaded_identity(settings: Settings, use_llm: bool, *, method: str,
                       jd_text: str, jd_upload, resumes, alias, gate,
                       approved_jd: JDReviewDraft | None = None) -> tuple[str, tuple[str, ...]]:
    """Compute a private, content-bound identity; no CV text is retained."""
    jd_bytes = (jd_text.encode("utf-8") if method.startswith("Paste") else
                jd_upload.getvalue())
    context = assessment_context_key(
        settings, jd_bytes=jd_bytes,
        approved_aliases_bytes=alias.getvalue() if alias is not None else b"",
        eligibility_policy_bytes=gate.getvalue() if gate is not None else b"",
        use_llm=use_llm,
    )
    context = _approval_context_key(context, approved_jd)
    keys = tuple(candidate_resume_keys([
        (safe_upload_name(item.name), item.getvalue()) for item in resumes]))
    return context, keys


def _approval_context_key(base: str, approved_jd: JDReviewDraft | None) -> str:
    """Changing a reviewed criterion invalidates completed-CV resume state."""
    if approved_jd is None:
        return base
    digest = hashlib.sha256(json.dumps(
        [r.model_dump(mode="json") for r in approved_jd.requirements],
        sort_keys=True, ensure_ascii=False,
    ).encode("utf-8")).hexdigest()
    return hashlib.sha256(f"{base}:{digest}".encode()).hexdigest()


def _prepare_jd_from_upload(settings: Settings, use_llm: bool, *,
                            method: str, jd_text: str, jd_upload) -> tuple[JDReviewDraft, str]:
    with tempfile.TemporaryDirectory(prefix="cvr_jd_review_") as temp_dir:
        root = Path(temp_dir)
        if method.startswith("Paste"):
            path = root / "job_description.txt"
            path.write_bytes(jd_text.encode("utf-8"))
        else:
            path = save_uploaded_bytes(root=root, group="jd", index=1,
                                       filename=jd_upload.name, data=jd_upload.getvalue())
        ranker = CVRanker(settings=settings, use_llm=use_llm, unified=use_llm)
        return ranker.prepare_jd_review(path), extract_text(path)


def _checkpoint_matches(identity: tuple[str, tuple[str, ...]], checkpoint) -> bool:
    """Require the same JD/config AND the same exact candidate file set."""
    if not isinstance(checkpoint, dict) or checkpoint.get("context_key") != identity[0]:
        return False
    prior = checkpoint.get("candidates", {})
    return (isinstance(prior, dict) and len(prior) == len(identity[1])
            and set(prior) == set(identity[1]))


def _checkpoint_digest(checkpoint: dict) -> str:
    """Bind an in-flight worker to the exact published partial assessment."""
    return hashlib.sha256(json.dumps(checkpoint, sort_keys=True,
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def _run_uploaded_inputs(settings: Settings, use_llm: bool, semantic_enabled: bool, *,
                         method: str, jd_text: str, jd_upload, resumes, alias, gate,
                         resume: bool, approved_jd: JDReviewDraft | None = None) -> RankingReport:
    """Run a user-authorized batch from the current widgets; keep bytes temporary."""
    with tempfile.TemporaryDirectory(prefix="cvr_upload_") as temp_dir:
        root = Path(temp_dir)
        if method.startswith("Paste"):
            jd = root / "job_description.txt"
            # Match the exact text bytes used by _uploaded_identity. Windows
            # write_text() can translate LF into CRLF and invalidate a perfectly
            # unchanged checkpoint, preventing automatic resume from arming.
            jd.write_bytes(jd_text.encode("utf-8"))
        else:
            jd = save_uploaded_bytes(root=root, group="jd", index=1,
                                     filename=jd_upload.name, data=jd_upload.getvalue())
        paths = [save_uploaded_bytes(root=root, group="resumes", index=i,
                                     filename=file.name, data=file.getvalue())
                 for i, file in enumerate(resumes, 1)]
        options = {}
        if alias:
            path = root / "approved_equivalences.json"
            path.write_bytes(alias.getvalue())
            options["approved_aliases_path"] = str(path)
        if gate:
            path = root / "eligibility_policy.json"
            path.write_bytes(gate.getvalue())
            options["eligibility_policy_path"] = str(path)
        configured = Settings(**{**settings.__dict__, **options})
        return _rank(jd, paths, configured, use_llm, "Uploaded CVs",
                     uploaded=True, semantic_enabled=semantic_enabled, resume=resume,
                     approved_jd=approved_jd)


def _recovery_input_snapshot(*, method: str, jd_text: str, jd_upload,
                             resumes, alias, gate) -> dict:
    """Copy immutable inputs before scheduling; no live widgets in a worker."""
    def upload(item):
        return ({"name": safe_upload_name(item.name), "data": item.getvalue()}
                if item is not None else None)

    return {
        "method": method, "jd_text": jd_text,
        "jd_upload": upload(jd_upload),
        "resumes": [upload(item) for item in resumes],
        "alias": upload(alias), "gate": upload(gate),
    }


def _background_resume(settings: Settings, approved_jd: JDReviewDraft,
                       snapshot: dict, checkpoint: dict | None,
                       use_llm: bool = True, progress_queue: SimpleQueue | None = None) -> dict:
    """Run a frozen-JD assessment/recovery on a worker; never touch Streamlit.

    Only in-memory copies of the original uploads travel to this worker.
    The temporary files are erased when the worker returns or raises.
    """
    with tempfile.TemporaryDirectory(prefix="cvr_background_") as temp_dir:
        root = Path(temp_dir)
        if snapshot["method"].startswith("Paste"):
            jd = root / "job_description.txt"
            jd.write_bytes(snapshot["jd_text"].encode("utf-8"))
        else:
            item = snapshot["jd_upload"]
            jd = save_uploaded_bytes(root=root, group="jd", index=1,
                                     filename=item["name"], data=item["data"])
        paths = [save_uploaded_bytes(root=root, group="resumes", index=index,
                                     filename=item["name"], data=item["data"])
                 for index, item in enumerate(snapshot["resumes"], 1)]
        options = {}
        for key, filename, option in (
            ("alias", "approved_equivalences.json", "approved_aliases_path"),
            ("gate", "eligibility_policy.json", "eligibility_policy_path"),
        ):
            item = snapshot[key]
            if item is not None:
                policy_path = root / filename
                policy_path.write_bytes(item["data"])
                options[option] = str(policy_path)
        configured = Settings(**{**settings.__dict__, **options})
        return _rank_core(jd, paths, configured, use_llm, uploaded=True,
                          resume=checkpoint is not None, approved_jd=approved_jd,
                          previous=checkpoint,
                          progress_callback=(progress_queue.put if progress_queue else None))


def _arm_auto_resume(report: RankingReport, settings: Settings, use_llm: bool,
                     identity: tuple[str, tuple[str, ...]], enabled: bool) -> str | None:
    """Schedule provider-aware recovery only for an LLM-validated frozen JD."""
    st.session_state.pop("cv_auto_resume_state", None)
    if not enabled or not use_llm or settings.llm_provider != "openrouter":
        return None
    if all(candidate.primary_score is not None for candidate in report.candidates):
        return None
    if report.jd_validation_mode != "llm_validated":
        return ("Automatic resume was not armed because JD extraction used a "
                "structural fallback. Run a fresh assessment after the provider recovers.")
    if st.session_state.get("cv_provider_hard_stop"):
        return ("Automatic resume was not armed because OpenRouter rejected "
                "the credentials, credits, or model access. Resolve the provider "
                "problem before retrying.")
    if st.session_state.get("cv_request_metrics", {}).get(
            "assessment_http_attempts_remaining") == 0:
        return ("Automatic recovery was not armed because this approved JD/CV "
                "checkpoint reached its configured cloud request budget. "
                "Previous verified results remain available.")
    saved = st.session_state.get("cv_resume_cache", {})
    if saved.get("context_key") != identity[0]:
        return "Automatic resume was not armed because the input checkpoint changed."
    now = time.monotonic()
    cooldown = st.session_state.get("cv_provider_cooldown", {})
    provider_wait = (max(0.0, cooldown.get("until", 0) - now)
                     if cooldown.get("provider") == settings.llm_provider
                     and cooldown.get("model") == settings.model_name else 0.0)
    initial_429 = bool(st.session_state.get("cv_request_metrics", {}).get("http_429_count"))
    st.session_state["cv_auto_resume_state"] = {
        "context_key": identity[0], "candidate_keys": identity[1],
        "attempts": 0, "rate_limit_streak": int(initial_429),
        "no_progress_streak": 0,
        "next_due": now + max(60.0 if initial_429 else 15.0, provider_wait),
        "running": False, "paused": False,
    }
    return None


def _review_jd_panel(settings: Settings, pending: dict) -> JDReviewDraft | None:
    """Render an explicit, editable approval gate before any candidate scoring."""
    draft = JDReviewDraft.model_validate(pending["draft"])
    _section_title("Step 3 · Review extracted JD requirements",
                   "Confirm the extracted criteria before they become the scoring reference.",
                   eyebrow="Job description")
    st.caption("Edit requirements and priorities if needed, then approve. JD quotations must match the source.")
    if draft.jd_validation_mode != "llm_validated":
        st.warning("This extraction used a structural fallback. Review all rows carefully; "
                   "the assessment will keep that extraction mode visible.")
    approved_data = pending.get("approved")
    if approved_data is not None:
        approved = JDReviewDraft.model_validate(approved_data)
        by_bucket = {bucket: sum(requirement_bucket(r) == bucket for r in approved.requirements)
                     for bucket in ("experience", "education", "jd_required", "jd_preferred")}
        st.success(f"JD approved and frozen · "
                   f"JD {by_bucket['jd_required'] + by_bucket['jd_preferred']} "
                   f"(Required {by_bucket['jd_required']} + Preferred {by_bucket['jd_preferred']}) "
                   f"· Experience {by_bucket['experience']} "
                   f"· Education {by_bucket['education']}.")
        st.dataframe(editable_jd_rows(approved), width="stretch", hide_index=True)
        if st.button("Edit the approved requirements", key="cv_jd_unlock_approval"):
            pending["draft"] = approved.model_copy(update={"approved": False}).model_dump()
            pending["approved"] = None
            pending["revision"] = int(pending.get("revision", 0)) + 1
            st.session_state["cv_jd_review_pending"] = pending
            st.session_state.pop("cv_auto_resume_state", None)
            st.rerun()
        return approved
    reviewed_rows = st.data_editor(
        editable_jd_rows(draft), num_rows="dynamic", hide_index=True,
        width="stretch", key=f"cv_jd_review_grid_{pending.get('revision', 0)}",
        disabled=["ID", "Minimum years", "Degree level", "Field of study"],
        column_config={
            "Priority": st.column_config.SelectboxColumn(
                "Priority", options=["required", "preferred", "unknown"], required=True),
            "Type": st.column_config.SelectboxColumn(
                "Type", options=["skill", "experience", "education", "certification",
                                 "license", "responsibility", "eligibility", "other"], required=True),
            "JD source": st.column_config.TextColumn("Exact JD quotation", width="large", required=True),
            "Requirement": st.column_config.TextColumn("Requirement", width="large", required=True),
        },
    )
    if st.button("Approve and freeze these JD requirements", type="primary",
                 key="cv_jd_freeze_approval"):
        try:
            approved = approve_jd_rows(
                draft=draft, rows=(reviewed_rows if isinstance(reviewed_rows, list)
                                   else reviewed_rows.to_dict("records")),
                jd_text=pending["source_text"], max_requirements=settings.max_requirements,
            )
            pending["approved"] = approved.model_dump()
            st.session_state["cv_jd_review_pending"] = pending
            st.session_state.pop("cv_auto_resume_state", None)
            st.rerun()
        except (ValueError, TypeError) as exc:
            st.error(f"Cannot approve the edited JD: {exc}")
    return None


def _run_form(settings: Settings, use_llm: bool, semantic_enabled: bool):
    _section_title("Step 1 · Upload documents",
                   "Add the employer's job description and the resumes to compare.",
                   eyebrow="Start assessment")
    st.caption("Upload documents · Extract JD · Approve requirements · Assign weightage · Assess candidates")
    with st.container(border=True):
        st.markdown("**Job description**")
        method = st.radio("JD source", ["Paste job description", "Upload JD file"],
                          horizontal=True, label_visibility="collapsed", key="cv_jd_source_mode")
        jd_text = ""
        jd_upload = None
        if method == "Paste job description":
            jd_text = st.text_area("Job description", placeholder="Paste the required and preferred skills, duties, and qualifications...", height=175, label_visibility="collapsed", key="cv_jd_text")
        else:
            jd_upload = st.file_uploader("JD file", type=SUPPORTED_UPLOAD_TYPES, accept_multiple_files=False, key="jd_file")

        st.markdown("**Candidate resumes**")
        resumes = st.file_uploader("CV files", type=SUPPORTED_UPLOAD_TYPES, accept_multiple_files=True, key="resume_files", help="PDF, Word, TXT or Markdown; scanned PDF images without text are not supported.")

        alias = st.session_state.get("approved_aliases")
        gate = st.session_state.get("eligibility_gates")
        auto_enabled = bool(st.session_state.get("cv_auto_resume_enabled", False))
        if auto_enabled and use_llm and settings.llm_provider == "openrouter":
            st.caption("Cloud auto-retry enabled · additional provider requests may incur charges.")

        current_report = st.session_state.get("cv_ranking_report")
        can_resume = bool(st.session_state.get("cv_resume_cache") and
                          isinstance(current_report, dict) and
                          (not use_llm or current_report.get("jd_validation_mode") == "llm_validated") and
                          any(row.get("primary_score") is None
                              for row in current_report.get("candidates", [])))
    # Keep Step 2 as a genuine heading, visible even after JD approval.
    # Earlier builds put this label inside the upload box, so the setup
    # appeared to jump directly from the Step 1 heading to Step 3.
    _section_title("Step 2 · Extract JD requirements",
                   "Identify the exact requirements that will be reviewed and scored.",
                   eyebrow="Job description")
    clicked = st.button("Extract JD requirements for review", type="primary",
                        width="stretch")

    if clicked:
        cooldown = st.session_state.get("cv_provider_cooldown", {})
        if (settings.llm_provider == "openrouter"
                and cooldown.get("provider") == settings.llm_provider
                and cooldown.get("model") == settings.model_name):
            seconds = cooldown.get("until", 0) - time.monotonic()
            if seconds > 0:
                st.warning(f"OpenRouter recently returned HTTP 429. Wait about "
                           f"{int(seconds) + 1} seconds before another assessment attempt. "
                           "Existing verified results remain available.")
                return
        if method.startswith("Paste") and len(jd_text.strip()) < 20:
            st.error("Enter a job description with at least 20 characters.")
            return
        if not method.startswith("Paste") and jd_upload is None:
            st.error("Select a job description file.")
            return
        uploads = ([jd_upload] if jd_upload else [])
        if any(int(getattr(f, "size", 0)) > MAX_FILE_BYTES for f in uploads):
            st.error("Each document must be 10 MB or smaller.")
            return
        if any(x is not None and int(getattr(x, "size", 0)) > 64 * 1024 for x in (alias, gate)):
            st.error("Optional policy JSON files cannot exceed 64 KB.")
            return
        try:
            identity = _uploaded_identity(settings, use_llm, method=method,
                                          jd_text=jd_text, jd_upload=jd_upload,
                                          resumes=[], alias=alias, gate=gate)
            with st.spinner("Extracting and classifying the JD · no CV is assessed yet..."):
                draft, source_text = _prepare_jd_from_upload(
                    settings, use_llm, method=method, jd_text=jd_text, jd_upload=jd_upload)
            st.session_state["cv_jd_review_pending"] = {
                "kind": "upload", "context_key": identity[0],
                "source_text": source_text, "draft": draft.model_dump(),
                "approved": None, "revision": time.monotonic_ns(),
            }
            st.session_state.pop("cv_auto_resume_state", None)
            st.rerun()
        except (DocumentError, OSError, RuntimeError, ValueError) as exc:
            st.error(f"Could not extract the JD: {exc}")
        except Exception as exc:
            st.error(f"JD extraction failed: {type(exc).__name__}: {exc}")

    pending = st.session_state.get("cv_jd_review_pending")
    approved = None
    if isinstance(pending, dict):
        if pending.get("kind") == "upload":
            try:
                identity = _uploaded_identity(settings, use_llm, method=method,
                                              jd_text=jd_text, jd_upload=jd_upload,
                                              resumes=[], alias=alias, gate=gate)
                valid = pending.get("context_key") == identity[0]
            except (AttributeError, TypeError, ValueError):
                valid = False
        else:
            # Demo flows are no longer offered in the supervisor-facing UI.
            valid = False
        if not valid:
            st.session_state.pop("cv_jd_review_pending", None)
            st.session_state.pop("cv_auto_resume_state", None)
            st.info("The JD or assessment settings changed. Extract the JD again before approval.")
            pending = None
        else:
            approved = _review_jd_panel(settings, pending)

    analyze_clicked = False
    resume_clicked = False
    weights_valid = True
    if approved is not None and pending is not None:
        weights_valid = _weightage_panel(approved.requirements)
        _section_title("Step 6 · Assess candidates against the approved JD",
                       "Run the evidence checks using your confirmed requirements and weights.",
                       eyebrow="Candidate screening")
        st.caption("You can change the CV selection without re-extracting the approved JD. "
                   "Changing the JD or assessment settings invalidates approval.")
        recovery_state = st.session_state.get("cv_auto_resume_state")
        recovery_future = st.session_state.get("cv_auto_resume_future")
        recovery_active = (isinstance(recovery_state, dict)
                           and not recovery_state.get("paused"))
        recovery_running = isinstance(recovery_future, Future) and not recovery_future.done()
        manual_pending = isinstance(st.session_state.get("cv_manual_assessment_state"), dict)
        analyze_clicked = st.button("Analyze CVs against approved JD", type="primary",
                                    key="cv_assess_approved", width="stretch",
                                    disabled=recovery_active or recovery_running or manual_pending)
        if manual_pending:
            st.caption("Candidate assessment is running in the background. Saved results remain accessible.")
        if recovery_active:
            st.caption("Automatic recovery is scheduled or running. Completed CVs remain saved.")
            if st.button("Pause automatic retries", key="cv_pause_recovery", width="stretch"):
                recovery_state["paused"] = True
                recovery_state["pause_reason"] = "paused by evaluator"
                st.session_state["cv_auto_resume_state"] = recovery_state
                st.rerun()
        if can_resume and not recovery_active:
            resume_clicked = st.button(
                "Resume unfinished assessments", width="stretch",
                help="Reuses verified results only when the approved JD, CVs and settings match.",
                disabled=recovery_running or manual_pending,
            )

    if analyze_clicked or resume_clicked:
        if not weights_valid:
            st.error("Allocate exactly 100 marks before scoring candidates.")
            return
        if approved is None:
            st.error("Extract and approve the JD requirements before assessing CVs.")
            return
        if pending["kind"] == "upload":
            if not resumes or len(resumes) > MAX_RESUMES:
                st.error(f"Upload between 1 and {MAX_RESUMES} resumes.")
                return
            if any(int(getattr(f, "size", 0)) > MAX_FILE_BYTES for f in resumes):
                st.error("Each resume must be 10 MB or smaller.")
                return
        try:
            identity = _uploaded_identity(
                settings, use_llm, method=method, jd_text=jd_text,
                jd_upload=jd_upload, resumes=resumes, alias=alias, gate=gate,
                approved_jd=approved)
            compatible = _checkpoint_matches(identity, st.session_state.get("cv_resume_cache"))
            if resume_clicked and not compatible:
                raise ValueError("Cannot resume: approved JD, candidates or settings changed.")
            effective_resume = resume_clicked or (analyze_clicked and can_resume and compatible)
            cooldown = st.session_state.get("cv_provider_cooldown", {})
            remaining = (float(cooldown.get("until", 0)) - time.monotonic()
                         if settings.llm_provider == "openrouter"
                         and cooldown.get("provider") == settings.llm_provider
                         and cooldown.get("model") == settings.model_name else 0)
            if effective_resume and remaining > 0:
                st.warning(f"OpenRouter is cooling down. Resume in approximately "
                           f"{int(remaining) + 1} seconds; the saved results are safe.")
            else:
                snapshot = _recovery_input_snapshot(
                    method=method, jd_text=jd_text, jd_upload=jd_upload,
                    resumes=resumes, alias=alias, gate=gate)
                prior_checkpoint = (deepcopy(st.session_state.get("cv_resume_cache"))
                                    if effective_resume else None)
                st.session_state["cv_manual_assessment_state"] = {
                    "context_key": identity[0], "candidate_keys": identity[1],
                    "checkpoint_digest": (_checkpoint_digest(prior_checkpoint)
                                          if prior_checkpoint is not None else None),
                }
                manual_progress = SimpleQueue()
                st.session_state["cv_manual_progress_queue"] = manual_progress
                st.session_state["cv_manual_progress_started"] = time.monotonic()
                st.session_state.pop("cv_manual_progress_queue_latest", None)
                st.session_state["cv_manual_assessment_future"] = _RECOVERY_POOL.submit(
                    _background_resume, settings, approved, snapshot,
                    prior_checkpoint, use_llm, manual_progress)
                st.info("Candidate assessment started in the background. "
                        "You can inspect already saved results while it runs.")
        except (DocumentError, OSError, RuntimeError, ValueError) as exc:
            st.error(f"Could not complete ranking: {exc}")
        except Exception as exc:
            st.error(f"Run failed: {type(exc).__name__}: {exc}")

    if st.session_state.get("cv_ranking_report") is not None:
        partial = any(c.get("primary_score") is None for c in
                      st.session_state["cv_ranking_report"].get("candidates", []))
        st.button("View partial results →" if partial else "Continue to Results →",
                  type="primary", width="stretch",
                  key="cv_open_results_after_assessment", on_click=_open_page,
                  args=("02  Rankings & evidence",))


@st.fragment(run_every="5s")
def _manual_assessment_fragment(settings: Settings, use_llm: bool) -> None:
    """Publish a finished initial/manual assessment only after input revalidation."""
    state = st.session_state.get("cv_manual_assessment_state")
    future = st.session_state.get("cv_manual_assessment_future")
    if not isinstance(state, dict) or not isinstance(future, Future):
        return
    if not future.done():
        with st.status("Assessing candidates in the background", state="running", expanded=True):
            st.write(_progress_caption("cv_manual_progress_queue", "cv_manual_progress_started"))
            st.caption("The Streamlit script is idle while the worker waits for the model. "
                       "The visible running indicator reflects the active assessment, "
                       "not a blocked browser session.")
        return

    st.session_state.pop("cv_manual_assessment_state", None)
    st.session_state.pop("cv_manual_assessment_future", None)
    st.session_state.pop("cv_manual_progress_queue", None)
    st.session_state.pop("cv_manual_progress_started", None)
    try:
        pending = st.session_state.get("cv_jd_review_pending")
        if not isinstance(pending, dict) or not pending.get("approved"):
            st.warning("Completed work was discarded because JD approval changed.")
            return
        approved = JDReviewDraft.model_validate(pending["approved"])
        identity = _uploaded_identity(
            settings, use_llm,
            method=st.session_state.get("cv_jd_source_mode", ""),
            jd_text=st.session_state.get("cv_jd_text", ""),
            jd_upload=st.session_state.get("jd_file"),
            resumes=st.session_state.get("resume_files") or [],
            alias=st.session_state.get("approved_aliases"),
            gate=st.session_state.get("eligibility_gates"),
            approved_jd=approved)
        if (identity[0] != state["context_key"]
                or identity[1] != tuple(state["candidate_keys"])):
            st.warning("Completed work was discarded because the JD, candidates "
                       "or assessment settings changed while it was running.")
            return
        prior_digest = state.get("checkpoint_digest")
        if (prior_digest is not None and prior_digest != _checkpoint_digest(
                st.session_state.get("cv_resume_cache") or {})):
            st.warning("Completed recovery was discarded because its original "
                       "assessment checkpoint was replaced.")
            return
        artifacts = future.result()
        _publish_rank_artifacts(artifacts, settings, use_llm, "Uploaded CVs", True)
        report = artifacts["report"]
        enabled = bool(st.session_state.get("cv_auto_resume_enabled", False))
        notice = _arm_auto_resume(report, settings, use_llm, identity, enabled)
        complete = sum(c.primary_score is not None for c in report.candidates)
        if complete == len(report.candidates):
            st.success("All candidate assessments are complete.")
        else:
            st.warning(f"Saved {complete}/{len(report.candidates)} completed CVs. "
                       "Incomplete evidence remains available for inspection.")
            if notice:
                st.info(notice)
    except (DocumentError, OSError, RuntimeError, ValueError) as exc:
        st.error(f"Candidate assessment could not complete: {exc}")
    except Exception as exc:
        st.error(f"Candidate assessment failed: {type(exc).__name__}")
    st.rerun()


def _advance_recovery_state(state: dict, report: RankingReport, *,
                            previous_complete: int, metrics: dict,
                             provider_hard_stop: bool, cooldown_seconds: float,
                             previous_verified: int = 0,
                             candidate_diagnostics: dict | None = None) -> dict | None:
    """Bound retries by actual verified progress, including repeated HTTP 429s."""
    state = dict(state)
    state["attempts"] = int(state.get("attempts", 0)) + 1
    current_complete = sum(c.primary_score is not None for c in report.candidates)
    if current_complete == len(report.candidates):
        return None
    if provider_hard_stop:
        state["paused"] = True
        state["pause_reason"] = "OpenRouter credentials, credits, or model access require attention"
        return state
    current_verified = sum(a.assessment_state == "verified"
                           for candidate in report.candidates
                           for a in candidate.assessments)
    progress = (current_complete > previous_complete
                or current_verified > previous_verified)
    rate_limited = bool(metrics.get("http_429_count"))
    # The pipeline has already tried a grouped correction and an independent
    # final verification before returning these unresolved IDs. Repeating the
    # same frozen evidence with the same model is not a provider cooldown; a
    # second full automatic retry would waste more calls without a new input.
    if not progress and not rate_limited and candidate_diagnostics:
        deterministic = []
        for index, details in candidate_diagnostics.items():
            if not isinstance(details, dict):
                continue
            unresolved = list(details.get("unresolved_ids") or [])
            cause = str(details.get("interrupted_cause") or "")
            if unresolved and (not cause or any(
                    token in cause for token in (
                        "ModelStructuredResponseError", "ModelOutputTruncatedError",
                        "structured JSON", "output truncated"))):
                deterministic.append((index, unresolved))
        if deterministic:
            state["paused"] = True
            state["pause_reason"] = (
                "the same requirements remained unverified after source/response validation "
                + "; ".join(f"CV {int(index) + 1}: {', '.join(ids[:6])}"
                            for index, ids in deterministic)
                + ". Automatic identical requests stopped to protect the cloud budget; "
                "inspect each requirement's cited evidence and the Execution details")
            return state
    state["no_progress_streak"] = (
        0 if progress else int(state.get("no_progress_streak", 0)) + 1)
    state["rate_limit_streak"] = (
        int(state.get("rate_limit_streak", 0)) + 1 if rate_limited else 0)
    max_streak = (_MAX_RATE_LIMITED_NO_PROGRESS if rate_limited
                  else _MAX_OTHER_NO_PROGRESS)
    if state["no_progress_streak"] >= max_streak:
        state["paused"] = True
        state["pause_reason"] = (
            f"{state['no_progress_streak']} retries made no progress; "
            + ("OpenRouter kept returning HTTP 429. Check your rate limit or daily quota"
               if rate_limited else
               "inspect the model response and CV evidence diagnostics"))
        return state
    if rate_limited:
        fallback = min(3600.0, 60.0 * (2 ** min(state["rate_limit_streak"] - 1, 6)))
        delay = max(fallback, cooldown_seconds,
                    float(metrics.get("provider_retry_after_seconds") or 0))
        # A multi-hour/day quota reset should not look like a hung assessment.
        if delay > 3600:
            state["paused"] = True
            state["pause_reason"] = (
                "OpenRouter requested a wait over one hour. Retry after the provider resets")
            return state
    else:
        delay = max(cooldown_seconds, 15.0 if progress else 60.0)
    state["next_due"] = time.monotonic() + delay
    return state


@st.fragment(run_every="5s")
def _automatic_resume_fragment(settings: Settings, use_llm: bool,
                               semantic_enabled: bool) -> None:
    """Opted-in, non-blocking recovery with provider-aware waiting.

    The worker can finish a call while the UI stays interactive. Results are
    published only after the live session's original inputs are revalidated.
    The scheduler requires a connected session for subsequent attempts; this
    is not an always-on server-side queue after logout/restart.
    """
    state = st.session_state.get("cv_auto_resume_state")
    if not isinstance(state, dict):
        st.session_state.pop("cv_auto_resume_future", None)
        return
    future = st.session_state.get("cv_auto_resume_future")
    if not (st.session_state.get("cv_auto_resume_enabled") and use_llm
            and settings.llm_provider == "openrouter"):
        if not isinstance(future, Future):
            st.session_state.pop("cv_auto_resume_state", None)
            return
        # The already-authorized call may still complete. Preserve its
        # verified results but do not schedule further requests.
        state["paused"] = True
        state["pause_reason"] = "automatic retries were disabled"
        st.session_state["cv_auto_resume_state"] = state
    if state.get("paused") and future is None:
        st.warning("Automatic recovery paused: "
                   + str(state.get("pause_reason") or "a non-recoverable error or repeated invalid results")
                   + ". Completed assessments are saved. Resume manually after resolving the issue.")
        return
    if isinstance(future, Future) and not future.done():
        with st.status("Recovering unfinished CV assessments", state="running", expanded=True):
            st.write(_progress_caption("cv_auto_progress_queue", "cv_auto_progress_started"))
            st.caption("Previously verified rows remain saved. This worker may wait for "
                       "the model, network timeout, or provider retry interval.")
        return
    remaining = float(state.get("next_due", 0)) - time.monotonic()
    if future is None and remaining > 0 and not state.get("paused"):
        st.caption(f"Automatic recovery pending · next attempt in approximately "
                   f"{int(remaining) + 1} seconds. Keep this browser tab connected.")
        return

    method = st.session_state.get("cv_jd_source_mode", "")
    jd_text = st.session_state.get("cv_jd_text", "")
    jd_upload = st.session_state.get("jd_file")
    resumes = st.session_state.get("resume_files") or []
    alias = st.session_state.get("approved_aliases")
    gate = st.session_state.get("eligibility_gates")
    pending = st.session_state.get("cv_jd_review_pending")
    if not isinstance(pending, dict) or pending.get("kind") != "upload" or not pending.get("approved"):
        st.session_state.pop("cv_auto_resume_state", None)
        st.warning("Automatic recovery stopped: the approved JD is no longer available.")
        return
    approved_jd = JDReviewDraft.model_validate(pending["approved"])
    if (not resumes or (method.startswith("Paste") and len(jd_text.strip()) < 20)
            or (not method.startswith("Paste") and jd_upload is None)):
        st.session_state.pop("cv_auto_resume_state", None)
        st.warning("Automatic recovery canceled because the original uploaded inputs are unavailable.")
        return
    try:
        current_identity = _uploaded_identity(
            settings, use_llm, method=method, jd_text=jd_text,
            jd_upload=jd_upload, resumes=resumes, alias=alias, gate=gate,
            approved_jd=approved_jd)
        checkpoint = st.session_state.get("cv_resume_cache") or {}
        if (current_identity[0] != state.get("context_key")
                or current_identity[1] != tuple(state.get("candidate_keys", ()))
                or checkpoint.get("context_key") != state.get("context_key")
                or len(checkpoint.get("candidates", {})) != len(resumes)):
            st.session_state.pop("cv_auto_resume_state", None)
            st.warning("Automatic recovery canceled: one or more CVs, the JD, "
                       "model, or assessment settings changed.")
            return
        report_data = st.session_state.get("cv_ranking_report")
        if not report_data:
            st.session_state.pop("cv_auto_resume_state", None)
            return
        prior = RankingReport.model_validate(report_data)
        if (prior.jd_validation_mode != "llm_validated" or
                all(c.primary_score is not None for c in prior.candidates)):
            st.session_state.pop("cv_auto_resume_state", None)
            return
    except (ValueError, KeyError, TypeError, AttributeError):
        st.session_state.pop("cv_auto_resume_state", None)
        st.warning("Automatic recovery canceled because the original checkpoint could not be validated.")
        return

    if isinstance(future, Future):
        st.session_state.pop("cv_auto_resume_future", None)
        st.session_state.pop("cv_auto_progress_queue", None)
        st.session_state.pop("cv_auto_progress_started", None)
        if (state.get("checkpoint_digest") is not None and
                state["checkpoint_digest"] != _checkpoint_digest(checkpoint)):
            st.session_state.pop("cv_auto_resume_state", None)
            st.warning("An earlier report was restored or replaced while recovery was running. "
                       "The previous background result was discarded.")
            return
        try:
            artifacts = future.result()
            # Checkpoint and inputs have just been revalidated above; the
            # worker does not directly mutate the visible assessment.
            _publish_rank_artifacts(artifacts, settings, use_llm, "Uploaded CVs", True)
            state["running"] = False
            if state.get("paused"):
                st.session_state["cv_auto_resume_state"] = state
            else:
                next_state = _advance_recovery_state(
                    state, artifacts["report"],
                    previous_complete=int(state.get("previous_complete", 0)),
                    previous_verified=int(state.get("previous_verified", 0)),
                    metrics=artifacts["request_metrics"],
                    provider_hard_stop=artifacts["provider_hard_stop"],
                    cooldown_seconds=float(artifacts["cooldown_seconds"]),
                    candidate_diagnostics=artifacts.get("unified_metrics"),
                )
                if next_state is None:
                    st.session_state.pop("cv_auto_resume_state", None)
                    st.success("All remaining CVs have been assessed.")
                else:
                    st.session_state["cv_auto_resume_state"] = next_state
        except Exception:
            state["paused"] = True
            state["running"] = False
            state["pause_reason"] = "a local processing error requires review"
            st.session_state["cv_auto_resume_state"] = state
            st.warning("Background recovery stopped after a technical error. "
                       "Previously verified results remain available.")
        st.rerun()
        return

    if state.get("paused"):
        return
    # Submit once, then return immediately; there is no synchronous network
    # request or Streamlit API call inside the background worker.
    snapshot = _recovery_input_snapshot(
        method=method, jd_text=jd_text, jd_upload=jd_upload,
        resumes=resumes, alias=alias, gate=gate)
    state["previous_complete"] = sum(c.primary_score is not None for c in prior.candidates)
    state["previous_verified"] = sum(a.assessment_state == "verified"
                                     for candidate in prior.candidates
                                     for a in candidate.assessments)
    state["checkpoint_digest"] = _checkpoint_digest(checkpoint)
    state["running"] = True
    st.session_state["cv_auto_resume_state"] = state
    automatic_progress = SimpleQueue()
    st.session_state["cv_auto_progress_queue"] = automatic_progress
    st.session_state["cv_auto_progress_started"] = time.monotonic()
    st.session_state.pop("cv_auto_progress_queue_latest", None)
    st.session_state["cv_auto_resume_future"] = _RECOVERY_POOL.submit(
        _background_resume, settings, approved_jd, snapshot, deepcopy(checkpoint),
        True, automatic_progress)
    st.info("Recovery started in the background. Saved results remain accessible.")


def _summary(report: RankingReport):
    successful = [c for c in report.candidates if c.primary_score is not None]
    bucket_totals = criterion_bucket_counts(report)
    required = bucket_totals["jd_required"]["total"]
    preferred = bucket_totals["jd_preferred"]["total"]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Candidates", len(report.candidates))
    m2.metric("JD criteria", required + preferred)
    m3.metric("Required / Preferred", f"{required} / {preferred}")
    m4.metric("CVs fully assessed", f"{len(successful)}/{len(report.candidates)}")
    if len(successful) != len(report.candidates):
        diagnostics = st.session_state.get("cv_unified_metrics") or {}
        for index, candidate in enumerate(report.candidates):
            if candidate.primary_score is not None:
                continue
            detail = diagnostics.get(str(index), {})
            pending_ids = [item.requirement_id for item in candidate.assessments
                           if item.assessment_state == "unverified"]
            cause = detail.get("interrupted_cause") if isinstance(detail, dict) else None
            validation_notes = (
                [str(note) for note in detail.get("warnings", [])
                 if any(str(note).startswith(rid + ":") for rid in pending_ids)
                 and "unresolved after grouped correction" not in str(note)]
                if isinstance(detail, dict) else [])
            if not cause and candidate.errors:
                cause = candidate.errors[-1]
            st.warning(
                f"{candidate.candidate_name} · not ranked yet. "
                + (f"{len(pending_ids)} requirement(s) still need a verified decision. "
                   if pending_ids else "The assessment did not finish. ")
                + "Completed results are saved. Open the details below to review what is missing.")
            if pending_ids:
                with st.expander(f"Review unfinished requirements for {candidate.candidate_name}"):
                    if cause:
                        st.caption("Technical cause: " + str(cause)[:250])
                    if validation_notes:
                        for note in list(dict.fromkeys(validation_notes))[:8]:
                            st.caption(note)
                    else:
                        st.info("The model did not return a source-validated judgment for every "
                                "criterion. The exact API response is unavailable in this saved "
                                "assessment; no conclusion was inferred from that failure.")
                    for assessment in candidate.assessments:
                        if assessment.requirement_id not in pending_ids:
                            continue
                        requirement = next((req for req in report.requirements
                                            if req.requirement_id == assessment.requirement_id), None)
                        label = requirement.name if requirement is not None else assessment.requirement_id
                        st.markdown(f"**{label}**")
                        st.caption(f"JD reference: {assessment.requirement_id}")
                        for passage in assessment.evidence_segments[:2]:
                            st.caption("Evidence examined: " + passage.text[:500])
    separate = [f"Experience: {bucket_totals['experience']['total']}"
                if bucket_totals["experience"]["total"] else "",
                f"Education: {bucket_totals['education']['total']}"
                if bucket_totals["education"]["total"] else ""]
    if any(separate):
        st.caption("Scored separately from JD requirements · " + " · ".join(x for x in separate if x))
    st.caption(f"{st.session_state.get('cv_run_label', 'Last run')} · {st.session_state.get('cv_run_provider','Provider not recorded')}")
    resume_stats = st.session_state.get("cv_request_metrics", {})
    if resume_stats.get("resumed_frozen_jd"):
        st.info(f"Resumed from the frozen JD: {resume_stats.get('reused_completed_candidates', 0)} "
                "completed candidate(s) reused without additional LLM calls; "
                f"{resume_stats.get('reassessed_candidates', 0)} candidate(s) retried.")
    prior_runs = st.session_state.get("cv_run_history", [])
    if prior_runs:
        with st.expander(f"Previous runs in this browser session ({len(prior_runs)})"):
            for index, snapshot in enumerate(prior_runs):
                title = snapshot.get("cv_run_label", "Previous analysis")
                recorded = snapshot.get("cv_ranking_report", {})
                count = len(recorded.get("candidates", []))
                left, right = st.columns([4, 1])
                left.caption(f"{title} · {count} candidates")
                if right.button("Restore", key=f"cv_restore_run_{index}"):
                    _restore_archived_run(st.session_state, index)
                    st.rerun()
    if len(report.requirements) >= st.session_state.get("cv_run_requirement_limit", 10**9):
        st.warning("The JD reached the configured requirement-processing limit. Check the frozen requirements below before relying on this ranking.")
    if report.warnings:
        with st.expander(f"Pipeline warnings ({len(report.warnings)})"):
            for warning in report.warnings:
                st.warning(warning)
    if report.jd_review_approved:
        st.caption("JD approved" + (" · edited by reviewer" if report.jd_review_edited else ""))


def _ranking(report: RankingReport):
    _section_title("Candidate leaderboard",
                   "Compare validated match scores under the approved JD priorities.",
                   eyebrow="Rankings & evidence")
    try:
        weights = _current_weights(report)
    except ValueError as exc:
        st.error(f"Cannot compute weighted scores: {exc}")
        return
    st.caption("Scores use the JD priorities you approved. Related (Transferable) skills do not earn points.")
    category_totals = criterion_bucket_counts(report)
    has_experience = category_totals["experience"]["total"] > 0
    has_education = category_totals["education"]["total"] > 0
    baseline = {row["Candidate index"]: row for row in final_leaderboard_rows(
        report, st.session_state.get("cv_final_results"))}
    try:
        calculated = weighted_leaderboard(report, weights)
    except ValueError as exc:
        st.error(f"Invalid requirement allocations: {exc}")
        return
    comparison = comparative_reasoning(report, weights,
                                      st.session_state.get("cv_final_results"),
                                      st.session_state.get("cv_source_ledgers"))
    reasons = {int(item["candidate_index"]): item for item in comparison["candidates"]}
    present = []
    for item in calculated:
        earlier = baseline[int(item["candidate_index"])]
        row = {
            "Rank": str(item["rank"]) if item["rank"] is not None else "Withheld",
            "Candidate": item["candidate"],
            "Score": item["weighted_score"],
        }
        if has_experience:
            row["Experience"] = item["experience"]
        if has_education:
            row["Education"] = item["education"]
        row.update({
            "JD matched": item["jd_overall"],
        })
        if st.session_state.get("cv_weight_split", False):
            row.update({"Required JD": item["required"],
                        "Preferred JD": item["preferred"]})
        row.update({"Transferable": earlier["Transferable"],
                    "Review": earlier["Review"], "Mode": earlier["Mode"],
                    "Why this rank": reasons[int(item["candidate_index"])].get(
                        "placement_reason", reasons[int(item["candidate_index"])]["summary"])})
        present.append(row)
    if calculated and not any(r["weighted_score"] is not None for r in calculated):
        st.warning("No final rank is available yet. One or more assessments may be incomplete.")
    with st.expander("How these scores are calculated", expanded=False):
        st.caption("Required and Preferred requirements share the JD scoring allocation. "
                   "Experience and Education use their own allocations; Transferable never earns points.")
        if calculated:
            first_breakdown = next((r["breakdown"] for r in calculated if r["weighted_score"] is not None), None)
            if first_breakdown:
                effective = first_breakdown["effective_weights"]
                st.write("**Effective category weights**")
                st.caption(" · ".join(
                    f"{name.replace('_', ' ').title()} {weight:.1f}%"
                    for name, weight in effective.items() if weight > 0))
    st.dataframe(present, hide_index=True, width="stretch", column_config={
        "Score": st.column_config.ProgressColumn("Weighted score", min_value=0, max_value=100, format="%.1f%%"),
        "Why this rank": st.column_config.TextColumn("Why this rank", width="large"),
    })
    _section_title("Why candidates ranked this way",
                   "One clear explanation per candidate. Detailed evidence is available below.",
                   eyebrow="Ranking explained")
    for explanation in comparison["candidates"]:
        _rank_explanation_row(explanation)
    with st.expander("Optional · Compare the leading candidate with others", expanded=False):
        _insight_card("Why this candidate ranks first" if comparison["top_candidate_indices"]
                      else "Why no ranking is available", comparison["summary"],
                      label="Head-to-head comparison", tone="blue")
        if comparison["comparisons"]:
            selected_comparison = st.selectbox(
                "Compare against",
                range(len(comparison["comparisons"])),
                format_func=lambda i: comparison["comparisons"][i]["against"],
                key="cv_rank_comparison_candidate",
            )
            selected = comparison["comparisons"][selected_comparison]
            st.metric("Weighted score difference", f"{selected['score_gap']:.2f} points")
            if selected["is_tie"]:
                st.info("These candidates have the same weighted score. Neither is arbitrarily preferred.")
            left_advantage, right_advantage = st.columns(2)
            with left_advantage:
                st.markdown("**Where the leader has additional verified matches**")
                for item in selected["top_candidate_advantages"]:
                    st.write(f"**{item['requirement']}** · {_scored_points_text(item['possible_points'])}"
                             f" — {item['why']}")
                if not selected["top_candidate_advantages"]:
                    st.caption("No additional Found requirements in this comparison.")
            with right_advantage:
                st.markdown("**Where the other candidate has additional verified matches**")
                for item in selected["other_candidate_advantages"]:
                    st.write(f"**{item['requirement']}** · {_scored_points_text(item['possible_points'])}"
                             f" — {item['why']}")
                if not selected["other_candidate_advantages"]:
                    st.caption("No additional Found requirements in this comparison.")
        else:
            st.caption("A head-to-head comparison becomes available when more than one candidate has a verified rank.")
    st.caption("For every requirement's full explanation and exact CV passages, use the individual candidate review below.")
    a, b = st.columns(2)
    output = io.StringIO()
    fields = ["Rank", "Candidate", "Score"]
    if has_experience:
        fields.append("Experience")
    if has_education:
        fields.append("Education")
    fields.append("JD matched")
    if st.session_state.get("cv_weight_split", False):
        fields.extend(["Required JD", "Preferred JD"])
    fields.extend(["Transferable", "Review", "Mode", "Why this rank"])
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows(present)
    a.download_button("Ranking summary (CSV)", output.getvalue().encode("utf-8-sig"), "cv_ranking_summary.csv", "text/csv", width="stretch")
    b.download_button("Full assessment (JSON)", report_json_bytes(report), "cv_ranking_evidence.json", "application/json", width="stretch")
    st.download_button(
        "Download everything — all candidates, JD, evidence & weighted scores (ZIP)",
        complete_results_zip(
            report, weights,
            final_results=st.session_state.get("cv_final_results"),
            source_ledgers=st.session_state.get("cv_source_ledgers"),
            technical={
                "run_label": st.session_state.get("cv_run_label"),
                "provider": st.session_state.get("cv_run_provider"),
                "request_metrics": st.session_state.get("cv_request_metrics", {}),
                "evidence_metrics": st.session_state.get("cv_unified_metrics", {}),
                "semantic_review": st.session_state.get("cv_semantic_report"),
                "source_ledger_errors": st.session_state.get("cv_source_ledger_errors", {}),
            },
        ),
        file_name="cv_ranker_complete_results.zip", mime="application/zip",
        type="primary", width="stretch",
    )


def _candidate_evidence(report: RankingReport):
    _section_title("Final JD-to-CV assessment",
                   "Inspect each candidate's decisions, supporting evidence, and reasoning.",
                   eyebrow="Individual candidate review")
    if report.build_id != BUILD_ID:
        st.error(
            f"This displayed report was assessed with build {report.build_id}, "
            f"but the running application is {BUILD_ID}. The previous model "
            "decisions are retained for audit; installing a new version does "
            "not recalculate them. Use Clear result, then Analyze and rank "
            "candidates to obtain decisions from the current build.")
    if not report.candidates:
        st.info("No candidates to inspect.")
        return
    options = list(range(len(report.candidates)))
    def fmt(i):
        c = report.candidates[i]
        return c.candidate_name
    index = st.selectbox("Choose a candidate", options, format_func=fmt, key="cv_candidate_selector")
    candidate = report.candidates[index]
    if candidate.primary_score is None:
        if candidate.assessments:
            st.warning("Ranking withheld because one or more requirements are unverified. "
                       "Verified requirement decisions remain visible below; the "
                       "candidate has no final percentage or leaderboard rank.")
        else:
            st.error("Candidate assessment failed before individual requirements could "
                     "be validated. No final score or rank is available.")
            # Make the failure cause visible without requiring the reviewer to
            # discover a collapsed technical expander. These errors come from
            # the provider's sanitized failure path or generic exception type.
            for detail in candidate.errors[:2]:
                if "Unified candidate assessment unavailable:" in detail:
                    st.warning(detail.split("Unified candidate assessment unavailable:", 1)[1][:350])
                else:
                    st.warning("Candidate processing stopped unexpectedly. "
                               "Inspect the assessment notices for diagnostics.")
    source_ledger = st.session_state.get("cv_source_ledgers", {}).get(str(index), [])
    final = st.session_state.get("cv_final_results", {}).get(str(index))
    if final is None:
        final = reconcile_candidate(report, index, source_ledger,
                                    st.session_state.get("cv_semantic_report"))
        st.warning("This older session has no persisted focused checks. Rerun the analysis for the full consolidated result.")
    buckets = criterion_bucket_counts(report, candidate)
    jd_found = buckets["jd_required"]["found"] + buckets["jd_preferred"]["found"]
    jd_total = buckets["jd_required"]["total"] + buckets["jd_preferred"]["total"]
    a, b, c = st.columns(3)
    a.metric("JD matched", f"{jd_found}/{jd_total}")
    b.metric("Transferable (not counted as matched)", final["Transferable"])
    try:
        weighted = weighted_candidate(report, candidate, _current_weights(report))
        c.metric("Weighted score", f"{weighted['score']:.1f}%" if weighted["score"] is not None else "—")
    except ValueError:
        c.metric("Weighted score", "—")
    try:
        explanation = candidate_reasoning(
            report, index, _current_weights(report),
            {**(st.session_state.get("cv_final_results") or {}), str(index): final},
            st.session_state.get("cv_source_ledgers"))
    except ValueError as exc:
        st.error(f"Cannot validate individual ranking reasoning: {exc}")
    else:
        _section_title("Why this CV received its ranking",
                       "What helped this candidate's score, and what held it back.",
                       eyebrow="Evidence-based ranking explanation")
        _insight_card(
            f"{candidate.candidate_name} · ranking rationale", explanation["summary"],
            label="Assessment summary",
            tag=(f"Rank #{explanation['rank']} · {explanation['weighted_score']:.2f}%"
                 if explanation["weighted_score"] is not None and explanation["rank"] is not None
                 else "Assessment incomplete · no score"),
            tone="teal" if explanation["weighted_score"] is not None else "amber",
        )
        strengths_column, gaps_column = st.columns(2, gap="medium")
        with strengths_column:
            st.markdown('<div class="cv-mini-title">✓ What helped this CV</div>',
                        unsafe_allow_html=True)
            if explanation["strengths"]:
                for item in explanation["strengths"][:4]:
                    _evidence_tile(item)
            else:
                st.caption("No verified Found requirement evidence is available yet.")
        with gaps_column:
            st.markdown('<div class="cv-mini-title">◇ What reduced the match</div>',
                        unsafe_allow_html=True)
            if explanation["gaps"]:
                for item in explanation["gaps"][:4]:
                    _evidence_tile(item, gap=True)
            else:
                st.caption("No Not Found criteria are recorded in this assessment.")
        if explanation["transferable"]:
            st.caption("Related but non-scoring capabilities: " + ", ".join(
                item["requirement"] for item in explanation["transferable"]))
        if explanation["audit"]["status"] == "needs_review":
            st.warning("Some explanation details need an audit review. The validated scoring "
                       "has not been changed; technical diagnostics are in Technical details.")
    if st.session_state.get("cv_weight_split", False):
        st.caption(f"JD breakdown · Required {buckets['jd_required']['found']}/{buckets['jd_required']['total']} "
                   f"· Preferred {buckets['jd_preferred']['found']}/{buckets['jd_preferred']['total']} "
                   "· Requirement points follow your editable allocations.")
    separate = [f"Experience {buckets['experience']['found']}/{buckets['experience']['total']}"
                if buckets["experience"]["total"] else "",
                f"Education {buckets['education']['found']}/{buckets['education']['total']}"
                if buckets["education"]["total"] else ""]
    if any(separate):
        st.caption("Separately scored · " + " · ".join(x for x in separate if x))
    if candidate.primary_score is None:
        st.caption(f"Partial evidence review only: {final.get('Unverified', 0)} "
                   "unverified criterion/criteria. Do not compare these counts "
                   "as a completed score or rank.")
    if not any(r.constraint.kind == "experience" and r.constraint.minimum_years is not None
               for r in report.requirements):
        st.caption("Experience note: the approved JD has no numeric minimum-years criterion, "
                   "so no professional-tenure threshold was scored.")
    if not any(r.constraint.kind == "education" for r in report.requirements):
        st.caption("Education note: the approved JD has no degree or field-of-study requirement, "
                   "so education did not affect the score.")
    if candidate.errors:
        with st.expander(f"Assessment and validation notices ({len(candidate.errors)})",
                         expanded=candidate.evaluation_mode == "failed"):
            st.caption("The source and deterministic validation notices from this candidate's assessment.")
            for error in candidate.errors:
                st.warning(error)
    # Do not show a blanket provisional warning for a completed assessment.
    # Transferable/uncertain criteria are marked for review at the specific
    # requirement below. Genuine incompleteness was already shown above.
    if candidate.primary_score is not None and final.get("Unverified"):
        st.error("One or more requirements remain unverified despite a saved overall score. "
                 "Do not use this rank until the assessment inconsistency is reviewed.")
    for notice in final.get("Notices", []):
        if notice not in candidate.errors:
            st.warning(notice)
    raw_error = st.session_state.get("cv_semantic_error")
    if raw_error:
        st.info(raw_error)
    filter_left, filter_right = st.columns([2, 1])
    with filter_left:
        status_filter = st.segmented_control("Show", ["All", "Found", "Transferable", "Not Found", "Unverified"], default="All", key="cv_candidate_status")
    group_names = {
        requirement.requirement_id: {
            "experience": "Experience", "education": "Education",
            "jd_required": "JD Required", "jd_preferred": "JD Preferred",
        }[requirement_bucket(requirement)]
        for requirement in report.requirements
    }
    with filter_right:
        group_filter = st.selectbox("Scoring category",
                                    ["All categories", "JD Required", "JD Preferred",
                                     "Experience", "Education"],
                                    key="cv_candidate_group")
    matrix = final["Criteria"]
    filtered = [item for item in matrix if (status_filter == "All" or item["Result"] == status_filter) and
                (group_filter == "All categories" or group_names.get(item["ID"]) == group_filter)]
    st.caption(f"Showing {len(filtered)} of {len(matrix)} requirements · "
               f"{sum(row['Review recommended'] for row in filtered)} review flags")
    # Exactly ONE final requirements table; no competing primary/shadow matrix.
    st.caption("'Why this decision' explains each JD-to-CV result. It is separate "
               "from the leaderboard's 'Why this rank'.")
    st.dataframe([{
        "ID": item["ID"], "JD requirement": item["Requirement"],
        "Priority": item["Priority"], "Category": group_names.get(item["ID"], ""),
        "Final decision": item["Result"],
        "Why this decision": item["Why"],
        "Cited segments": ", ".join(c["Segment"] for c in item.get("Display checkpoints", item["Checkpoints"])),
        "Review": "Suggested" if item["Review recommended"] else "",
    } for item in filtered], hide_index=True, width="stretch",
                 column_config={"Why this decision": st.column_config.TextColumn(
                     "Why this decision", width="large")})
    summary_columns = ["ID", "JD requirement", "Priority", "Category", "Final decision", "What the CV establishes", "Cited segments", "Checkpoints considered", "Review", "Why"]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=summary_columns)
    writer.writeheader()
    for item in matrix:
        writer.writerow({
            "ID": item["ID"], "JD requirement": item["Requirement"],
            "Priority": item["Priority"], "Category": group_names.get(item["ID"], ""),
            "Final decision": item["Result"],
            "What the CV establishes": item["Evidence level"],
            "Cited segments": ", ".join(c["Segment"] for c in item.get("Display checkpoints", item["Checkpoints"])),
            "Checkpoints considered": len(item["Checkpoints"]),
            "Review": "Review suggested" if item["Review recommended"] else "Source assessed",
            "Why": item["Why"],
        })
    left, right = st.columns(2)
    left.download_button("Download final decisions (CSV)", output.getvalue().encode("utf-8-sig"),
                         "cv_final_decisions.csv", "text/csv", width="stretch")
    right.download_button("Download all final evidence (JSON)",
                          json.dumps(final, ensure_ascii=False, indent=2),
                          "cv_final_evidence.json", "application/json", width="stretch")
    _section_title("Requirement evidence",
                   "Open any criterion to read why it was credited, transferred, or not established.",
                   eyebrow="JD-to-CV decisions")
    st.caption("Original source passages are shown beneath each explanation; the complete citation ledger is available in the JSON export.")
    for item in filtered:
        icon = {"Found": "✅", "Transferable": "↔️", "Not Found": "○", "Unverified": "⚠️"}[item["Result"]]
        visible_checkpoints = item.get("Display checkpoints", item["Checkpoints"])
        with st.expander(f"{icon} {item['Requirement']} · {item['Result']}"):
            st.caption(f"Requirement {item['ID']} · {group_names.get(item['ID'], item['Priority'])} "
                       f"· {len(visible_checkpoints)} cited CV passage(s)")
            st.caption("CV evidence: " + item["Evidence level"])
            if item["Review recommended"] and item["Result"] != "Unverified":
                st.caption("Human review suggested for this requirement; this note does not change its score.")
            _insight_card("Why this decision", item["Why"],
                          label="Individual criterion explanation", tag=item["Result"],
                          tone={"Found": "teal", "Transferable": "blue",
                                "Not Found": "slate", "Unverified": "amber"}.get(item["Result"], "slate"))
            st.caption("Original employer requirement: " + item["JD source"])
            if len(visible_checkpoints) < len(item["Checkpoints"]):
                st.caption(f"Showing {len(visible_checkpoints)} of {len(item['Checkpoints'])} checkpoints; see JSON for all.")
            if not item["Checkpoints"]:
                if item["Result"] == "Unverified":
                    st.info("Assessment incomplete: no source judgment was accepted. "
                            "This is neither evidence of absence nor a hiring decision.")
                else:
                    st.info("No relevant source passage was retained for this requirement.")
            for n, checkpoint in enumerate(visible_checkpoints, 1):
                st.markdown(f"**CV passage {n}**")
                st.caption(f"Source {checkpoint['Segment']} · CV section: {checkpoint['Section']} "
                           f"· {', '.join(checkpoint['Sources'])}")
                if not checkpoint["Validated against CV"]:
                    st.warning("One citation could not be verified against the retained original CV ledger; it cannot by itself establish a match.")
                st.markdown(f'<div class="cv-source">{highlighted_source_html(checkpoint["Text"], checkpoint.get("Highlight terms") or item["Requirement"])}</div>', unsafe_allow_html=True)
                for why in checkpoint["Why"]:
                    if why != item["Why"] and why not in item["Why"]:
                        st.caption("Why this segment matters: " + why)


def _jd_details(report: RankingReport):
    _section_title("Frozen JD requirements",
                   "The exact criteria approved for this assessment, preserved for audit.",
                   eyebrow="Approved employer criteria")
    if report.jd_review_approved:
        st.success("Evaluator-approved JD requirements" +
                   (" · reviewed edits applied" if report.jd_review_edited else " · extracted rows approved"))
    st.dataframe([{
        "ID": r.requirement_id,
        "Priority": r.priority.title(),
        "Scoring category": {
            "experience": "Experience", "education": "Education",
            "jd_required": "JD Required", "jd_preferred": "JD Preferred",
        }[requirement_bucket(r)],
        "Requirement": r.name,
        "Type": (f"{r.constraint.kind} · {r.constraint.experience_mode}"
                 if r.constraint.experience_mode else r.constraint.kind),
        "Minimum professional years": r.constraint.minimum_years,
        "Degree level": r.constraint.degree_level or "",
        "Field of study": r.constraint.field_of_study or "",
        "JD source": r.jd_evidence,
    } for r in report.requirements], width="stretch", hide_index=True)
    with st.expander("Download optional HR policy templates"):
        st.download_button("Blank equivalence approvals", json.dumps({"schema_version": 1, "approvals": []}, indent=2), "approved_equivalences_template.json", "application/json")
        required_names = [r.name for r in report.requirements if r.priority == "required"]
        template = {"schema_version": 1, "jd_sha256": report.jd_sha256, "reviewed_by": "REPLACE WITH APPROVED REVIEWER", "gates": [{"requirement": required_names[0], "reason": "REPLACE WITH EMPLOYER POLICY"}] if required_names else []}
        st.download_button("Eligibility template for this JD", json.dumps(template, indent=2), "eligibility_policy_template.json", "application/json", disabled=not bool(required_names))


def _semantic_review(report: RankingReport, *, candidate_name: str | None = None):
    """Same-run live semantic proposals, not a stale uploaded JSON report."""
    _section_title("Potential transferable skills",
                   "Optional AI relationships for human review; these do not change verified scoring.",
                   eyebrow="Capability cross-check")
    st.caption("AI-proposed relationships, independently unverified. The original score and ranking never change.")
    reason = st.session_state.get("cv_semantic_error")
    if reason:
        st.warning(reason)
    raw_retrieval = st.session_state.get("cv_semantic_retrieval")
    if isinstance(raw_retrieval, dict):
        completed = sum(item.get('retrieval_status') == 'completed'
                        for item in raw_retrieval.get('candidates', []))
        st.caption(f"Local semantic evidence retrieval: {completed}/"
                   f"{len(raw_retrieval.get('candidates', []))} candidate(s) completed. "
                   "These are search results, not independently verified matches.")
    raw = st.session_state.get("cv_semantic_report")
    if raw is None:
        if not reason:
            st.info("No semantic analysis was run. Enable the optional AI capability cross-check and analyze again. Local Ollama must have the EMBEDDING_MODEL from .env installed.")
        return
    from cv_ranker.semantic.transferability import TransferabilityShadowReport
    try:
        proposals = TransferabilityShadowReport.model_validate(raw)
    except Exception:
        st.error("Saved semantic report could not be validated. Rerun Analyze.")
        return
    if candidate_name is None:
        names = [c.candidate_name for c in report.candidates]
        candidate_name = st.selectbox("Candidate for semantic review", names, key="semantic_candidate")
    rows = semantic_candidate_rows(report, proposals, candidate_name)
    counts = {label: sum(r["Relationship"] == label for r in rows)
              for label in ("direct", "transferable", "uncertain", "related_only", "not_evidenced")}
    candidate = next((c for c in proposals.candidates if c.candidate_name == candidate_name), None)
    m1, m2, m3 = st.columns(3)
    m1.metric("Transferable (proposed)", counts["transferable"])
    m2.metric("Direct (proposed)", counts["direct"])
    m3.metric("Review flags", candidate.relationship_consistency_flag_count if candidate else 0)
    flagged_alternatives = [r for r in rows if r.get("Functional overlap review")]
    if counts["transferable"] == 0:
        st.caption("No transferable relationship was proposed by the model. This is not proof of no transferable experience.")
    if flagged_alternatives:
        st.info(f"{len(flagged_alternatives)} requirement(s) have alternative-work evidence worth manual functional review. "
                "These are review candidates, NOT verified transferable matches.")
    if not rows:
        st.info("No capability proposals available for this candidate.")
        return
    proposal_filter = st.selectbox(
        "Show AI proposals", ["All", "Transferable only", "Direct", "Uncertain", "Related only", "Not evidenced"],
        key=f"semantic_filter_{candidate_name}",
    )
    if proposal_filter == "All":
        # Transferable items first, but NEVER hide the other AI decisions.
        order = {"transferable": 0, "uncertain": 1, "related_only": 2,
                 "direct": 3, "not_evidenced": 4}
        rows = sorted(rows, key=lambda r: (order.get(r["Relationship"], 9),
                                         -int(r.get("Functional overlap review", False))))
    elif proposal_filter == "Transferable only":
        rows = [r for r in rows if r["Relationship"] == "transferable"]
        if not rows:
            st.caption("No transferable proposals. Switch to All to inspect the other decisions.")
    else:
        rows = [r for r in rows if r["Relationship"] == proposal_filter.lower().replace(" ", "_")]
    st.dataframe([{
        "Requirement": r["Requirement"], "Capability": r["Capability ID"],
        "Priority": r["Priority"],
        "AI relationship": r["Relationship"].replace("_", " ").title(),
        "Why": r["Explanation"],
        "Cited sources": r["Source IDs"],
        **({"Review flags": r["Review flags"]} if any(row["Review flags"] for row in rows) else {}),
    } for r in rows], hide_index=True, width="stretch")
    candidate_idx = next((index for index, original in enumerate(report.candidates)
                          if original.candidate_name == candidate_name), None)
    original_segments = {
        segment.segment_id: segment
        for segment in resume_segments(st.session_state.get("cv_source_ledgers", {}).get(str(candidate_idx), []))
    }
    primary_by_id = ({assessment.requirement_id: assessment
                      for assessment in report.candidates[candidate_idx].assessments}
                     if candidate_idx is not None else {})
    for r in rows:
        with st.expander(f"{r['Requirement']} · {r['Relationship'].replace('_', ' ').title()}"):
            st.caption(f"Frozen JD requirement: {r['Requirement ID']} · Actual assessed capability: {r['Capability ID']}")
            st.markdown("**Why the AI proposed this relationship**")
            st.write(r["Explanation"])
            primary = primary_by_id.get(r["Requirement ID"])
            if primary and r["Capability ID"] == r["Requirement ID"]:
                if primary.status == "matched" and r["Relationship"] in {"not_evidenced", "related_only", "uncertain"}:
                    st.warning("Primary V4 assessment says Matched, but the AI relationship review disagrees or is inconclusive. The primary evidence remains visible above; the proposal must not silently reverse it.")
                elif primary.status == "not_matched" and r["Relationship"] == "direct":
                    st.warning("AI review reports direct evidence where primary V4 says Not matched. Inspect both source paths; no automatic score change was made.")
            st.caption(f"Citation audit: {r['Citation audit'].replace('_', ' ')} · {len(r['Citations'])} exact cited source(s)")
            if not r["Citations"]:
                st.write("No source text was cited for this AI proposal. This does not establish that the skill is absent from the CV.")
            for checkpoint, citation in enumerate(r["Citations"], 1):
                source = original_segments.get(citation["segment_id"])
                st.markdown(f"**AI evidence checkpoint {checkpoint} · {citation['segment_id']}**")
                if source:
                    st.caption(f"Original CV section: {source.section} · Exact AI-cited quote shown below in full segment")
                    st.markdown(f'<div class="cv-source">{highlighted_source_html(source.text, citation["text"])}</div>', unsafe_allow_html=True)
                else:
                    st.caption("Exact model-cited quote; full source ledger unavailable in this session")
                    st.markdown(f'<div class="cv-source">{highlighted_source_html(citation["text"], None)}</div>', unsafe_allow_html=True)
            if r["Review flags"]:
                st.warning("Human review flags: " + r["Review flags"])
            if r.get("Functional overlap review") and r.get("Functional review note"):
                st.caption("Functional overlap observation: " + r["Functional review note"])
    st.caption("Direct means CV-reported evidence for the named requirement; transferable means possible comparable functionality, not the named tool. Neither label authenticates skills or changes eligibility.")


def _source_segments_page(report: RankingReport):
    """Full original CV source ledger for single-candidate evidence debugging."""
    _section_title("Complete CV source segments",
                   "Explore exact extracted passages, citations, and prioritized source text.",
                   eyebrow="Source transparency")
    if not report.candidates:
        st.info("No CV was analyzed yet.")
        return
    index = st.selectbox(
        "Inspect CV", list(range(len(report.candidates))),
        format_func=lambda i: report.candidates[i].candidate_name,
        key="cv_source_candidate",
    )
    raw = st.session_state.get("cv_source_ledgers", {}).get(str(index))
    if raw is None:
        error = st.session_state.get("cv_source_ledger_errors", {}).get(str(index))
        st.warning(error or "No source-segment ledger was retained for this analysis. Run the CV again to create one.")
        return
    segments = resume_segments(raw)
    if not segments:
        st.warning("The document yielded zero text segments. Check the PDF/DOCX extraction quality.")
        return
    candidate = report.candidates[index]
    primary = {citation.segment_id for assessment in candidate.assessments
               for citation in assessment.evidence_segments}
    selected_count = int(st.session_state.get("cv_unified_metrics", {}).get(
        str(index), {}).get("selected_sources", 0))
    selected_ids = set(st.session_state.get("cv_unified_metrics", {}).get(
        str(index), {}).get("selected_source_ids", []))
    st.caption(f"{len(segments)} extracted segments · {len(primary)} cited · {selected_count} prioritized")
    left, right = st.columns([2, 1])
    search = left.text_input("Find text in source", placeholder="e.g. Python, NLP, Cloud Run", key="cv_segment_search").casefold().strip()
    section = right.selectbox("CV section", ["All sections"] + sorted({segment.section for segment in segments}), key="cv_segment_section")
    shown = [segment for segment in segments if (not search or search in segment.text.casefold())
             and (section == "All sections" or section == segment.section)]
    st.caption(f"Showing {len(shown)} of {len(segments)}")
    st.dataframe([{
        "Segment": item.segment_id,
        "Section": item.section,
        "Primary citation": "Yes" if item.segment_id in primary else "",
        "Prioritized for assessment": "Yes" if item.segment_id in selected_ids else "",
        "Extracted source": item.text,
    } for item in shown], hide_index=True, width="stretch")
    with st.expander("Inspect one segment and its original lines", expanded=False):
        if shown:
            by_id = {segment.segment_id: segment for segment in shown}
            selected_id = st.selectbox("Segment", list(by_id), key="cv_source_detail_id")
            item = by_id[selected_id]
            st.markdown(f'<div class="cv-source">{highlighted_source_html(item.text, search or None)}</div>', unsafe_allow_html=True)
            if item.source_lines:
                st.code("\n".join(item.source_lines), language="text")
        else:
            st.caption("No segments match the filters.")
    st.download_button("Download all CV source segments (JSON)",
                       json.dumps(raw, ensure_ascii=False, indent=2),
                       "cv_source_segments.json", "application/json")


def _yake_display_rows(candidates) -> list[dict[str, object]]:
    """Show genuine YAKE extraction output in ranked order, without model credit."""
    ordered = sorted(candidates, key=lambda item: (item.score, item.keyword.casefold()))
    return [{"Rank": index, "JD phrase": item.keyword, "YAKE score": item.score}
            for index, item in enumerate(ordered, 1)]


def _reasoning_audit_panel(report: RankingReport) -> None:
    """Diagnostics are intentionally isolated from supervisor-facing ranking prose."""
    with st.expander("Reasoning verification · internal audit", expanded=False):
        st.caption("Technical consistency checks only. Passing these checks does not "
                   "independently verify a candidate's claims or prove the model's judgment.")
        try:
            weights = _current_weights(report)
            for index, candidate in enumerate(report.candidates):
                explanation = candidate_reasoning(
                    report, index, weights,
                    st.session_state.get("cv_final_results"),
                    st.session_state.get("cv_source_ledgers"),
                )
                audit = explanation["audit"]
                st.markdown(f"**{index + 1}. {candidate.candidate_name}**")
                st.caption(f"Reasoning check: {audit['status']} · "
                           f"{audit['checked_requirements']} criteria inspected")
                st.caption(audit["validation_scope"])
                for repair in audit["repairs"]:
                    st.warning(f"{repair['requirement_id']}: {'; '.join(repair['issues'])}")
                for warning in audit["warnings"]:
                    st.warning(warning)
                if not audit["repairs"] and not audit["warnings"]:
                    st.success("No structural discrepancies were detected in this assessment's explanation.")
        except ValueError as exc:
            st.error(f"Reasoning audit unavailable: {exc}")


def _technical(report: RankingReport):
    st.caption("Advanced diagnostics and source exports for auditing; no effect on scoring.")
    _reasoning_audit_panel(report)
    _section_title("JD phrase discovery · YAKE",
                   "Inspect the source phrases that helped structure the job description.",
                   eyebrow="Technical audit")
    yake_rows = _yake_display_rows(report.yake_candidates)
    if yake_rows:
        left, right = st.columns([1, 2])
        left.metric("Candidate phrases", len(yake_rows))
        right.metric("Highest-ranked phrase", yake_rows[0]["JD phrase"])
        st.caption("Extracted automatically from the JD. A smaller YAKE score means a stronger "
                   "phrase candidate; it is **not** a CV match, verified requirement or scoring point.")
        phrase_query = st.text_input("Find a JD phrase", placeholder="Search extracted phrases…",
                                     key="cv_yake_phrase_search")
        filtered_yake = [row for row in yake_rows
                         if phrase_query.strip().casefold() in str(row["JD phrase"]).casefold()]
        if filtered_yake:
            st.dataframe(filtered_yake, hide_index=True, width="stretch", height=280,
                         column_config={
                             "Rank": st.column_config.NumberColumn("Rank", format="%d"),
                             "YAKE score": st.column_config.NumberColumn(
                                 "YAKE score ↓", format="%.6f",
                                 help="Smaller values rank higher. Scores are not match percentages."),
                         })
        else:
            st.info("No YAKE phrase matches that search.")
        csv_content = io.StringIO()
        writer = csv.DictWriter(csv_content, fieldnames=["Rank", "JD phrase", "YAKE score"])
        writer.writeheader()
        writer.writerows(yake_rows)
        st.download_button("Download YAKE phrases (CSV)",
                           csv_content.getvalue().encode("utf-8-sig"),
                           "jd_yake_phrases.csv", "text/csv", width="stretch")
    else:
        st.info("No YAKE phrase candidates were recorded for this JD.")
    with st.expander("Execution details", expanded=False):
        st.write("**Provider used for this run:**", st.session_state.get("cv_run_provider", "Not recorded"))
        st.write("**JD validation:**", report.jd_validation_mode)
        st.write("**JD SHA256:**", report.jd_sha256)
        st.write("**Build:**", report.build_id)
        st.write("**Assessment protocol:**", ASSESSMENT_PROTOCOL)
        request_stats = st.session_state.get("cv_request_metrics")
        unified_stats = st.session_state.get("cv_unified_metrics")
        if isinstance(request_stats, dict) and request_stats:
            st.write("**Request budget and usage**")
            st.json(request_stats)
            st.caption("Actual attempts include provider retries; token totals are provider-reported "
                       "where available and may be zero when a provider omits usage data.")
        if isinstance(unified_stats, dict) and unified_stats:
            st.write("**Unified retrieval and assessment · per candidate:**")
            st.dataframe([{"Candidate": report.candidates[int(index)].candidate_name, **metrics}
                          for index, metrics in unified_stats.items()],
                         hide_index=True, width="stretch")
        raw_semantic = st.session_state.get("cv_semantic_report")
        local_retrieval = st.session_state.get("cv_semantic_retrieval")
        if isinstance(local_retrieval, dict):
            st.write("**Independent local semantic search:**")
            summary = [{
                "Candidate": row.get('candidate_name'),
                "Status": row.get('retrieval_status'),
                "Eligible CV segments": row.get('retrieval_eligible_count', 0),
                "Retrieved JD criteria": len(row.get('hits_by_requirement', {})),
                "Repaired cache vectors": row.get('cache_repaired_entries', 0),
            } for row in local_retrieval.get('candidates', [])]
            if summary:
                st.dataframe(summary, hide_index=True, width="stretch")
        if raw_semantic:
            try:
                from cv_ranker.semantic.transferability import TransferabilityShadowReport
                semantic = TransferabilityShadowReport.model_validate(raw_semantic)
                st.write("**Semantic review execution:**", "complete" if semantic.complete else "incomplete")
                st.write("**Adaptive model call batching:**")
                st.json(semantic.batching)
                st.caption("Batching statistics describe initial relationship calls; optional focused model rechecks and provider-internal retries are additional.")
                st.write("**Relationship consistency flags:**", semantic.relationship_consistency_flag_count)
            except Exception:
                st.warning("Saved semantic report is invalid; model call diagnostics unavailable")
    with st.expander("JD extraction diagnostics", expanded=False):
        st.json(report.jd_diagnostics)
        if report.approved_aliases:
            st.json(report.approved_aliases)
        if report.eligibility_policy_sha256:
            st.caption("HR eligibility policy: " + report.eligibility_policy_sha256)
    with st.expander("Download audit files", expanded=False):
        st.download_button("Complete assessment (JSON)",
                           report_json_bytes(report), "assessment_audit.json", "application/json")
        if raw_semantic:
            st.download_button("Download raw AI relationship proposals (audit JSON)",
                               json.dumps(raw_semantic, ensure_ascii=False, indent=2),
                               "raw_semantic_audit.json", "application/json")
        if isinstance(local_retrieval, dict):
            st.download_button("Download local semantic retrieval (sensitive JSON)",
                               json.dumps(local_retrieval, ensure_ascii=False, indent=2),
                               "local_semantic_retrieval.json", "application/json")
        final = st.session_state.get("cv_final_results", {})
        if final:
            st.download_button("Download reconciled decisions (all candidates)",
                               json.dumps(final, ensure_ascii=False, indent=2),
                               "all_final_decisions.json", "application/json")
    _jd_details(report)


def render_app():
    try:
        assert_runtime_current()
    except RuntimeError as exc:
        st.error(f"Source/package integrity check failed: {exc}")
        st.stop()
    _styles()
    settings, use_llm, semantic_enabled = _sidebar()
    st.markdown(
        '<div class="cv-hero" role="banner"><div>'
        '<div class="cv-hero-badge">Supervisor edition · Evidence-first screening</div>'
        '<h1 class="cv-hero-title">CV Ranker</h1>'
        '<p class="cv-hero-description">Review approved job requirements, compare candidates '
        'with transparent scores, and understand every decision through original CV evidence.</p>'
        '</div><div class="cv-hero-mark" aria-hidden="true">↗</div></div>',
        unsafe_allow_html=True,
    )
    if settings is None:
        st.stop()
    old_provider = st.session_state.get("cv_run_provider")
    now_provider = (f"{settings.llm_provider} · {settings.model_name}"
                    if use_llm else "offline exact fallback")
    if old_provider and old_provider != now_provider:
        st.warning(f"The displayed results were generated with {old_provider}. "
                   "Run Analyze again to apply your newly selected provider; "
                   "switching does not silently rescore an existing report.")

    setup, results, sources, review = st.tabs([
        "01  Analyze", "02  Rankings & evidence", "03  CV source segments", "04  Technical details",
    ], default="01  Analyze", key="cv_active_page", on_change="rerun")
    with setup:
        _run_form(settings, use_llm, semantic_enabled)
        _manual_assessment_fragment(settings, use_llm)
        _automatic_resume_fragment(settings, use_llm, semantic_enabled)
    with results:
        report = _get_report()
        if report is None:
            st.info("No ranking yet. Use Analyze to upload a job description and candidate resumes.")
        else:
            _summary(report)
            _ranking(report)
            st.divider()
            _candidate_evidence(report)
    with sources:
        report = _get_report()
        if report is None:
            st.info("Run an analysis first to inspect CV source segments.")
        else:
            _source_segments_page(report)
    with review:
        report = _get_report()
        if report is None:
            st.info("Run an analysis first to inspect technical details.")
        else:
            _technical(report)
    st.caption("Screening support only · Final hiring decisions require human review.")
