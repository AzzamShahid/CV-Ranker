import argparse
import sys
from pathlib import Path

from cv_ranker import CVRanker, Settings
from cv_ranker.documents import DocumentError, collect_resume_paths
from cv_ranker.report import print_report, write_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Explainable YAKE + LangChain/Ollama CV ranker"
    )
    parser.add_argument("--jd", required=True, help="JD file: TXT, MD, PDF or DOCX")
    parser.add_argument(
        "--resumes",
        required=True,
        nargs="+",
        help="Resume files and/or directories containing TXT, MD, PDF or DOCX files",
    )
    parser.add_argument("--output", default="outputs/ranking.json", help="JSON output path")
    parser.add_argument("--model", default="qwen2.5:3b", help="Ollama model name")
    parser.add_argument("--top-keywords", type=int, default=40, help="YAKE candidate count")
    parser.add_argument(
        "--max-requirements",
        type=int,
        default=30,
        help="Maximum frozen JD requirements retained for ranking",
    )
    parser.add_argument("--exact-initialism", action="store_true",
                        help="Opt in to literal initialism recovery (e.g. Natural Language Processing -> NLP)")
    parser.add_argument("--approved-aliases", default=None, metavar="FILE.json",
                        help="Optional human-reviewed, job-specific equivalence file (never auto-inferred)")
    parser.add_argument("--eligibility-policy", default=None, metavar="FILE.json",
                        help="Optional HR-reviewed gates bound to exact JD SHA256; no gates by default")
    parser.add_argument("--llm-type-review", action="store_true",
                        help="Experimental: ask Qwen to suggest types for ambiguous JD criteria; suggestions remain review-needed")
    parser.add_argument("--no-llm", action="store_true", help="Use deterministic fallback only")
    parser.add_argument("--details", action="store_true", help="Print per-requirement evidence")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    resumes = collect_resume_paths(args.resumes)
    if not resumes:
        print("ERROR: No supported resume files were found.", file=sys.stderr)
        return 2

    try:
        settings = Settings(
            model_name=args.model,
            yake_top_k=args.top_keywords,
            max_requirements=args.max_requirements,
            exact_initialism_guard=args.exact_initialism,
            approved_aliases_path=args.approved_aliases,
            llm_type_review=args.llm_type_review,
            eligibility_policy_path=args.eligibility_policy,
        )
        ranker = CVRanker(settings=settings, use_llm=not args.no_llm)
        report = ranker.run(Path(args.jd), resumes)
        write_json(report, args.output)
    except (DocumentError, RuntimeError, ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print_report(report, details=args.details)
    print(f"JSON report written to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
