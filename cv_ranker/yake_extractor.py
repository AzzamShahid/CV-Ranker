from .config import Settings
from .schemas import YakeCandidate


def extract_yake_candidates(text: str, settings: Settings) -> list[YakeCandidate]:
    try:
        import yake
    except ImportError as exc:
        raise RuntimeError(
            "YAKE is not installed. Run: pip install -r requirements.txt"
        ) from exc

    extractor = yake.KeywordExtractor(
        lan="en",
        n=settings.yake_max_ngram,
        dedupLim=settings.yake_dedup_threshold,
        top=settings.yake_top_k,
    )
    raw = extractor.extract_keywords(text)
    candidates = [
        YakeCandidate(keyword=str(keyword).strip(), score=float(score))
        for keyword, score in raw
        if str(keyword).strip()
    ]
    candidates.sort(key=lambda item: item.score)
    return candidates
