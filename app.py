import tempfile
from pathlib import Path

import streamlit as st

from cv_ranker import CVRanker, Settings
from cv_ranker.documents import DocumentError
from cv_ranker.schemas import RankingReport
from cv_ranker.ui_support import (
    ranking_rows,
    report_json_bytes,
    save_uploaded_bytes,
)


ROOT = Path(__file__).resolve().parent
SUPPORTED_UPLOAD_TYPES = ["txt", "md", "pdf", "docx"]
MAX_RESUMES = 25
MAX_FILE_BYTES = 10 * 1024 * 1024

st.set_page_config(
    page_title="Explainable CV Ranker",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .block-container {padding-top: 1.5rem; padding-bottom: 2rem;}
      div[data-testid="stMetricValue"] {font-size: 1.65rem;}
      .small-note {color: #6b7280; font-size: 0.9rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


def _store_report(report: RankingReport, label: str) -> None:
    st.session_state["ranking_report"] = report.model_dump()
    st.session_state["ranking_label"] = label


def _get_report() -> RankingReport | None:
    raw = st.session_state.get("ranking_report")
    if raw is None:
        return None
    try:
        return RankingReport.model_validate(raw)
    except Exception:
        st.session_state.pop("ranking_report", None)
        return None


def _run_ranker(
    *,
    jd_path: Path,
    resume_paths: list[Path],
    model_name: str,
    top_keywords: int,
    max_requirements: int,
    use_llm: bool,
    label: str,
    ephemeral_sources: bool = False,
) -> None:
    settings = Settings(
        model_name=model_name,
        yake_top_k=top_keywords,
        max_requirements=max_requirements,
    )
    ranker = CVRanker(settings=settings, use_llm=use_llm)
    report = ranker.run(jd_path, resume_paths)
    if ephemeral_sources:
        cleaned_candidates = []
        for candidate in report.candidates:
            source = Path(candidate.candidate_source) if candidate.candidate_source else None
            slot = source.parent.name if source is not None else "unknown"
            cleaned_candidates.append(
                candidate.model_copy(
                    update={
                        "candidate_source": f"uploaded://{slot}/{candidate.candidate_name}"
                    }
                )
            )
        report = report.model_copy(
            update={
                "job_description_source": "uploaded/pasted JD (temporary workspace)",
                "candidates": cleaned_candidates,
            }
        )
    _store_report(report, label)


def _render_results(report: RankingReport) -> None:
    st.divider()
    st.subheader("Ranking results")

    successful = [c for c in report.candidates if c.primary_score is not None]
    failed = [c for c in report.candidates if c.primary_score is None]
    top = successful[0] if successful else None

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Candidates", len(report.candidates))
    c2.metric("Frozen requirements", len(report.requirements))
    c3.metric("Successful evaluations", len(successful))
    c4.metric(
        "Top score",
        f"{top.primary_score:.2f}%" if top and top.primary_score is not None else "—",
    )

    mode_caption = st.session_state.get("ranking_label", "Last run")
    actual_modes = ", ".join(sorted({c.evaluation_mode for c in successful})) or "none"
    st.caption(
        f"{mode_caption} • JD validation: {report.jd_validation_mode} • "
        f"Actual candidate evaluation mode(s): {actual_modes} • "
        "Primary rank is calculated deterministically in Python. Equal primary scores share a rank; filename only orders tied rows for display."
    )

    if report.warnings:
        with st.expander(f"System warnings ({len(report.warnings)})", expanded=True):
            for warning in report.warnings:
                st.warning(warning)

    table_rows = ranking_rows(report)
    st.dataframe(
        table_rows,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Primary score": st.column_config.NumberColumn(format="%.2f%%"),
            "Required coverage": st.column_config.NumberColumn(format="%.2f%%"),
            "Preferred coverage": st.column_config.NumberColumn(format="%.2f%%"),
        },
    )

    st.download_button(
        "Download full JSON report",
        data=report_json_bytes(report),
        file_name="cv_ranking_report.json",
        mime="application/json",
        use_container_width=False,
    )

    tab_candidates, tab_requirements, tab_diagnostics = st.tabs(
        ["Candidate details", "JD requirements", "Diagnostics"]
    )

    with tab_candidates:
        if not report.candidates:
            st.info("No candidate results are available.")
        else:
            name_counts = {}
            for candidate_item in report.candidates:
                name_counts[candidate_item.candidate_name] = name_counts.get(candidate_item.candidate_name, 0) + 1

            def candidate_label(index: int) -> str:
                candidate_item = report.candidates[index]
                duplicate_suffix = ""
                if name_counts.get(candidate_item.candidate_name, 0) > 1:
                    duplicate_suffix = f" [{candidate_item.candidate_source}]"
                if (
                    candidate_item.rank is not None
                    and candidate_item.primary_score is not None
                ):
                    return (
                        f"#{candidate_item.rank} — {candidate_item.candidate_name} — "
                        f"{candidate_item.primary_score:.2f}%{duplicate_suffix}"
                    )
                return f"FAILED — {candidate_item.candidate_name}{duplicate_suffix} — item {index + 1}"

            selected_index = st.selectbox(
                "Candidate",
                options=list(range(len(report.candidates))),
                format_func=candidate_label,
            )
            candidate = report.candidates[selected_index]

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Rank", candidate.rank if candidate.rank is not None else "—")
            m2.metric(
                "Primary score",
                f"{candidate.primary_score:.2f}%"
                if candidate.primary_score is not None
                else "FAILED",
            )
            m3.metric(
                "Primary matched",
                f"{candidate.matched_primary}/{candidate.total_primary}",
            )
            m4.metric("Evaluation", candidate.evaluation_mode)

            coverage_bits = []
            if candidate.required_score is not None:
                coverage_bits.append(
                    f"Required: {candidate.matched_required}/{candidate.total_required} "
                    f"({candidate.required_score:.2f}%)"
                )
            if candidate.unknown_score is not None:
                coverage_bits.append(
                    f"Unknown priority: {candidate.matched_unknown}/{candidate.total_unknown} "
                    f"({candidate.unknown_score:.2f}%)"
                )
            if coverage_bits:
                st.caption(" • ".join(coverage_bits))

            if candidate.preferred_score is not None:
                st.caption(
                    "Preferred coverage is shown separately and does not inflate the "
                    "primary score when required requirements are available: "
                    f"{candidate.matched_preferred}/{candidate.total_preferred} "
                    f"({candidate.preferred_score:.2f}%)."
                )
            if candidate.score_basis:
                st.caption(f"Score basis: {candidate.score_basis}")

            if candidate.errors:
                with st.expander("Candidate warnings / errors", expanded=True):
                    for error in candidate.errors:
                        st.warning(error)

            by_id = {a.requirement_id: a for a in candidate.assessments}
            for requirement in report.requirements:
                assessment = by_id.get(requirement.requirement_id)
                if assessment is None:
                    continue

                if assessment.status == "matched":
                    icon = "✅"
                elif assessment.status == "uncertain":
                    icon = "⚠️"
                else:
                    icon = "❌"

                title = (
                    f"{icon} {requirement.name} — {assessment.status.replace('_', ' ').title()}"
                )
                with st.expander(title, expanded=assessment.status != "matched"):
                    st.markdown(f"**Priority:** `{requirement.priority}`")
                    st.markdown("**JD evidence**")
                    st.code(requirement.jd_evidence, language=None)
                    st.markdown("**Resume evidence**")
                    if assessment.evidence:
                        st.code(assessment.evidence, language=None)
                        if assessment.matched_term:
                            st.caption(f"Direct alias / OR term used: {assessment.matched_term}")
                    else:
                        st.write("No source evidence was accepted.")

    with tab_requirements:
        requirement_rows = [
            {
                "ID": r.requirement_id,
                "Priority": r.priority,
                "Requirement": r.name,
                "JD evidence": r.jd_evidence,
            }
            for r in report.requirements
        ]
        st.dataframe(requirement_rows, use_container_width=True, hide_index=True)

    with tab_diagnostics:
        st.markdown(f"**JD source:** `{report.job_description_source}`")
        st.markdown(f"**JD validation mode:** `{report.jd_validation_mode}`")
        st.markdown(f"**YAKE candidates:** {len(report.yake_candidates)}")
        if report.yake_candidates:
            st.dataframe(
                [
                    {"Keyword": item.keyword, "YAKE score": item.score}
                    for item in report.yake_candidates
                ],
                use_container_width=True,
                hide_index=True,
            )
        if failed:
            st.error(f"{len(failed)} candidate(s) failed evaluation.")


st.title("Explainable CV Ranking Engine")
st.write(
    "Upload one job description and multiple resumes. YAKE discovers JD keyphrases, "
    "Qwen validates JD requirements and evaluates each resume with contextual source evidence, "
    "while Python checks evidence relevance/tone and calculates the final ranking."
)

with st.sidebar:
    st.header("Runtime settings")
    use_llm = st.toggle(
        "Use local Qwen pipeline",
        value=True,
        help=(
            "Uses Ollama + qwen2.5:3b through LangChain for JD validation and normally one resume assessment call per CV. "
            "Very large requirement sets are batched only for context safety. If disabled, the conservative deterministic fallback is used."
        ),
    )
    model_name = st.text_input("Ollama model", value="qwen2.5:3b")
    top_keywords = st.slider("YAKE candidate phrases", 10, 200, 40, 10)
    max_requirements = st.slider("Maximum frozen requirements", 5, 100, 30, 5)
    st.caption(r"Run `.\.venv\Scripts\python.exe doctor.py --live` before an AI-backed presentation.")

st.subheader("1. Job description")
jd_mode = st.radio(
    "JD input",
    ["Paste text", "Upload file"],
    horizontal=True,
    label_visibility="collapsed",
)

jd_text = ""
jd_upload = None
if jd_mode == "Paste text":
    jd_text = st.text_area(
        "Paste the job description",
        height=230,
        placeholder="Paste the full job description here...",
    )
else:
    jd_upload = st.file_uploader(
        "Upload JD",
        type=SUPPORTED_UPLOAD_TYPES,
        accept_multiple_files=False,
    )

st.subheader("2. Candidate resumes")
resume_uploads = st.file_uploader(
    "Upload multiple resumes",
    type=SUPPORTED_UPLOAD_TYPES,
    accept_multiple_files=True,
    help="Supported: PDF, DOCX, TXT, Markdown. Image-only/scanned PDFs require OCR and are not supported in this MVP.",
)

col_run, col_clear = st.columns([3, 1])
with col_run:
    run_clicked = st.button(
        "Rank uploaded candidates",
        type="primary",
        use_container_width=True,
    )
with col_clear:
    if st.button("Clear results", use_container_width=True):
        st.session_state.pop("ranking_report", None)
        st.session_state.pop("ranking_label", None)
        st.rerun()

if run_clicked:
    input_error = None
    if jd_mode == "Paste text" and len(jd_text.strip()) < 20:
        input_error = "Paste a job description with at least 20 characters."
    elif jd_mode == "Upload file" and jd_upload is None:
        input_error = "Upload a job-description file."
    elif not resume_uploads:
        input_error = "Upload at least one resume."
    elif len(resume_uploads) > MAX_RESUMES:
        input_error = f"Upload at most {MAX_RESUMES} resumes per run for this demo build."
    elif jd_upload is not None and getattr(jd_upload, "size", 0) > MAX_FILE_BYTES:
        input_error = "The JD file exceeds the 10 MB demo limit."
    elif any(getattr(uploaded, "size", 0) > MAX_FILE_BYTES for uploaded in resume_uploads):
        input_error = "One or more resume files exceed the 10 MB demo limit."

    if input_error:
        st.error(input_error)
    else:
        try:
            with st.spinner("Evaluating candidates..."):
                with tempfile.TemporaryDirectory(prefix="cv_ranker_ui_") as temp_root:
                    temp_root_path = Path(temp_root)
                    if jd_mode == "Paste text":
                        jd_path = temp_root_path / "job_description.txt"
                        jd_path.write_text(jd_text, encoding="utf-8")
                    else:
                        assert jd_upload is not None
                        jd_path = save_uploaded_bytes(
                            root=temp_root_path,
                            group="jd",
                            index=1,
                            filename=jd_upload.name,
                            data=jd_upload.getvalue(),
                        )

                    resume_paths = [
                        save_uploaded_bytes(
                            root=temp_root_path,
                            group="resumes",
                            index=index,
                            filename=uploaded.name,
                            data=uploaded.getvalue(),
                        )
                        for index, uploaded in enumerate(resume_uploads, start=1)
                    ]

                    _run_ranker(
                        jd_path=jd_path,
                        resume_paths=resume_paths,
                        model_name=model_name,
                        top_keywords=top_keywords,
                        max_requirements=max_requirements,
                        use_llm=use_llm,
                        label=(
                            "Uploaded documents • local LLM requested"
                            if use_llm
                            else "Uploaded documents • deterministic fallback"
                        ),
                        ephemeral_sources=True,
                    )
            st.success("Ranking completed.")
        except (DocumentError, RuntimeError, ValueError, OSError) as exc:
            st.error(f"Ranking failed: {exc}")
        except Exception as exc:
            st.error(f"Unexpected UI/runtime failure: {exc}")

st.divider()
with st.expander("Bundled supervisor demos"):
    st.write(
        "These buttons use the exact same ranking engine and are useful as a presentation "
        "fallback if you do not want to upload files live."
    )
    demo_a, demo_b = st.columns(2)
    if demo_a.button("Run backend demo", use_container_width=True):
        try:
            with st.spinner("Running backend demo..."):
                _run_ranker(
                    jd_path=ROOT / "sample_data" / "backend_jd.txt",
                    resume_paths=sorted((ROOT / "sample_data" / "backend_resumes").glob("*.txt")),
                    model_name=model_name,
                    top_keywords=top_keywords,
                    max_requirements=max_requirements,
                    use_llm=use_llm,
                    label="Bundled backend demo",
                )
            st.success("Backend demo completed.")
        except Exception as exc:
            st.error(f"Backend demo failed: {exc}")
    if demo_b.button("Run HR demo", use_container_width=True):
        try:
            with st.spinner("Running HR demo..."):
                _run_ranker(
                    jd_path=ROOT / "sample_data" / "hr_jd.txt",
                    resume_paths=sorted((ROOT / "sample_data" / "hr_resumes").glob("*.txt")),
                    model_name=model_name,
                    top_keywords=top_keywords,
                    max_requirements=max_requirements,
                    use_llm=use_llm,
                    label="Bundled HR demo",
                )
            st.success("HR demo completed.")
        except Exception as exc:
            st.error(f"HR demo failed: {exc}")

report = _get_report()
if report is not None:
    _render_results(report)
else:
    st.info("Upload a JD and resumes, or run one of the bundled demos to see results here.")
