"""Optional read-only Phase 7G retrieval; no ranking or matching decisions."""
from .core import EvidenceSegment, CapabilityQuery, RetrievalHit, ShadowRetriever
from .embedding import OllamaEmbeddingGemma, EmbeddingError
from .cache import SQLiteVectorCache
from .integration import run_shadow_retrieval, retrieval_eligible_ids
from .decomposition import create_shadow_search_plan, JDSearchPlan, SearchCapability

__all__ = ["EvidenceSegment", "CapabilityQuery", "RetrievalHit", "ShadowRetriever", "OllamaEmbeddingGemma", "EmbeddingError", "SQLiteVectorCache", "run_shadow_retrieval", "retrieval_eligible_ids", "create_shadow_search_plan", "JDSearchPlan", "SearchCapability"]
