import argparse
import sys
from pathlib import Path
from time import perf_counter

from cv_ranker import CVRanker, Settings
from cv_ranker.assessor import assess_resume
from cv_ranker.documents import DocumentError, extract_text
from cv_ranker.jd import validate_jd_requirements
from cv_ranker.scoring import score_candidate
from cv_ranker.text_utils import canonical_key
from cv_ranker.yake_extractor import extract_yake_candidates


WIDTH = 92


def rule(char: str = "=") -> None:
    print(char * WIDTH)


def stage(number: int, title: str, purpose: str) -> None:
    print()
    rule()
    print(f"STAGE {number}: {title}")
    print(f"Purpose: {purpose}")
    rule()


def short(text: str | None, limit: int = 180) -> str:
    if not text:
        return "<none>"
    clean = " ".join(text.split())
    return clean if len(clean) <= limit else clean[: limit - 3] + "..."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Trace the real CV-ranker pipeline: document extraction -> YAKE -> "
            "JD validation -> one resume assessment -> Python scoring."
        )
    )
    parser.add_argument("--jd", help="JD file: TXT, MD, PDF or DOCX")
    parser.add_argument("--resume", help="Single resume file to trace in detail")
    parser.add_argument("--demo", choices=["backend", "hr"])
    parser.add_argument("--candidate")
    parser.add_argument("--model", default="qwen2.5:3b")
    parser.add_argument("--top-keywords", type=int, default=40)
    parser.add_argument("--max-requirements", type=int, default=30)
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--keyword-limit", type=int, default=20)
    return parser


def resolve_inputs(args: argparse.Namespace) -> tuple[Path, Path]:
    if args.demo:
        root = Path(__file__).resolve().parent / "sample_data"
        if args.demo == "backend":
            jd = root / "backend_jd.txt"
            folder = root / "backend_resumes"
            default_candidate = "01_strong.txt"
        else:
            jd = root / "hr_jd.txt"
            folder = root / "hr_resumes"
            default_candidate = "01_hr_strong.txt"
        resume = folder / (args.candidate or default_candidate)
        if not resume.exists():
            available = ", ".join(sorted(p.name for p in folder.iterdir() if p.is_file()))
            raise ValueError(
                f"Bundled candidate '{resume.name}' was not found. Available: {available}"
            )
        return jd, resume

    if not args.jd or not args.resume:
        raise ValueError("Provide either --demo or both --jd and --resume.")
    return Path(args.jd), Path(args.resume)


def main() -> int:
    args = build_parser().parse_args()
    try:
        jd_path, resume_path = resolve_inputs(args)
        settings = Settings(
            model_name=args.model,
            yake_top_k=args.top_keywords,
            max_requirements=args.max_requirements,
        )
        ranker = CVRanker(settings=settings, use_llm=not args.no_llm)

        rule()
        print("             CV RANKER - INTERNAL WORKING / SUPERVISOR TRACE")
        rule()
        print(f"JD:          {jd_path}")
        print(f"Resume:      {resume_path}")
        print(f"Model:       {settings.model_name if not args.no_llm else 'DISABLED (fallback)'}")
        print("Embeddings:  NONE")
        print("Vector DB:   NONE")
        print("Verifier:    FUTURE WORK - not active")
        print("Score owner: deterministic Python")

        if ranker.startup_warnings:
            print("Startup warnings:")
            for warning in ranker.startup_warnings:
                print(f"  - {warning}")

        stage(1, "DOCUMENT EXTRACTION", "Extract text from the JD and resume.")
        t0 = perf_counter()
        jd_text = extract_text(jd_path)
        resume_text = extract_text(resume_path)
        print(f"JD text:     {len(jd_text):,} characters")
        print(f"Resume text: {len(resume_text):,} characters")
        print(f"Elapsed:     {perf_counter() - t0:.3f}s")

        stage(2, "YAKE CANDIDATE DISCOVERY", "Generate candidate JD phrases. YAKE does not decide final requirements or scores.")
        t0 = perf_counter()
        try:
            yake_candidates = extract_yake_candidates(jd_text, settings)
        except Exception as exc:
            yake_candidates = []
            print(f"WARNING: YAKE unavailable; continuing with structural fallback: {exc}")
        print(
            f"YAKE: ngram<={settings.yake_max_ngram}, top_k={settings.yake_top_k}, "
            f"dedup={settings.yake_dedup_threshold}"
        )
        print(f"Extracted: {len(yake_candidates)} candidates in {perf_counter() - t0:.3f}s")
        print(f"{'#':>3}  {'YAKE SCORE':>12}  KEYWORD / KEYPHRASE")
        print("-" * WIDTH)
        for idx, item in enumerate(yake_candidates[: max(1, args.keyword_limit)], start=1):
            print(f"{idx:>3}  {item.score:>12.8f}  {item.keyword}")

        stage(3, "JD VALIDATION + FREEZING", "One LLM call validates actual hiring requirements, then Python freezes IDs and priorities.")
        t0 = perf_counter()
        requirements, jd_mode, jd_warnings = validate_jd_requirements(
            jd_text=jd_text,
            candidates=yake_candidates,
            settings=settings,
            llm=ranker.llm if ranker.use_llm else None,
        )
        print(f"Mode:                {jd_mode}")
        print(f"Frozen requirements: {len(requirements)}")
        print(f"Elapsed:             {perf_counter() - t0:.3f}s")
        for warning in jd_warnings:
            print(f"WARNING: {warning}")
        print()
        for req in requirements:
            print(f"[{req.requirement_id}] {req.priority.upper():9} {req.name}")
            print(f"      JD evidence: {short(req.jd_evidence)}")

        retained_keys = {canonical_key(req.name) for req in requirements}
        omitted = [
            item.keyword
            for item in yake_candidates
            if canonical_key(item.keyword) not in retained_keys
        ]
        if omitted:
            print()
            print("YAKE phrases not retained as exact final requirement names (diagnostic only):")
            for keyword in omitted[:12]:
                print(f"  - {keyword}")

        stage(4, "RESUME ASSESSMENT + PYTHON EVIDENCE CHECK", "One main LLM call evaluates all frozen requirements. Python checks source evidence; invalid rows get at most one corrective retry.")
        t0 = perf_counter()
        assessments, assessment_mode, assessment_warnings = assess_resume(
            resume_text=resume_text,
            requirements=requirements,
            llm=ranker.llm if ranker.use_llm else None,
        )
        print(f"Mode:    {assessment_mode}")
        print(f"Elapsed: {perf_counter() - t0:.3f}s")
        for warning in assessment_warnings:
            print(f"WARNING: {warning}")
        print()
        req_by_id = {req.requirement_id: req for req in requirements}
        for item in assessments:
            req = req_by_id[item.requirement_id]
            symbol = {"matched": "+", "uncertain": "?", "not_matched": "-"}[item.status]
            print(f"{symbol} [{item.requirement_id}] {req.name} -> {item.status}")
            print(f"      Evidence: {short(item.evidence)}")

        stage(5, "DETERMINISTIC PYTHON SCORING", "Count matched requirements. The LLM never creates the percentage or rank.")
        result = score_candidate(
            candidate_name=resume_path.name,
            candidate_source=str(resume_path),
            requirements=requirements,
            assessments=assessments,
            evaluation_mode=assessment_mode,
            errors=assessment_warnings,
        )
        print(f"Score basis: {result.score_basis}")
        if result.total_primary:
            print(
                f"Formula: {result.matched_primary}/{result.total_primary} x 100 = "
                f"{result.primary_score:.2f}%"
            )
        print(f"Primary score: {result.primary_score if result.primary_score is not None else 'N/A'}")
        if result.preferred_score is not None:
            print(
                f"Preferred coverage: {result.matched_preferred}/{result.total_preferred} "
                f"= {result.preferred_score:.2f}%"
            )

        stage(6, "ARCHITECTURE SUMMARY", "Show the responsibility of each component.")
        print("YAKE                -> candidate phrase discovery")
        print("Qwen JD call        -> actual JD requirement validation")
        print("Python              -> freeze requirement IDs and source checks")
        print("Qwen CV call        -> matched / not_matched / uncertain + source segment IDs")
        print("Python              -> resolve segment IDs + relevance + negation/learning guards")
        print("Corrective retry    -> only invalid evidence rows, at most once")
        print("Python scoring      -> ONLY component that creates percentages")
        print("Python sorting      -> final candidate order")
        if not args.no_llm:
            batches = max(1, -(-len(requirements) // settings.assessment_batch_size))
            base_calls = 1 + batches
            print(f"Normal live LLM calls for this trace: {base_calls} (1 JD + {batches} CV assessment batch(es)). Extra calls occur only for correction.")

        print()
        rule()
        print("TRACE COMPLETE")
        rule()
        return 0

    except (DocumentError, RuntimeError, ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
