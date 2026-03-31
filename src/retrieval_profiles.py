from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from datetime import datetime


@dataclass
class RetrievalProfile:
    profile_name: str
    display_name: str
    description: str
    is_system: bool
    is_active: bool
    
    bm25_weight: float
    pg_fts_weight: float
    pg_vec_weight: float
    
    use_reranker: bool
    reranker_model: Optional[str]
    normalize_scores: bool
    metadata_boost: float
    citation_graph_boost: float
    
    top_k: int
    bm25_limit: int
    fts_limit: int
    vec_limit: int
    
    id: Optional[int] = None
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "profile_name": self.profile_name,
            "display_name": self.display_name,
            "description": self.description,
            "is_system": self.is_system,
            "is_active": self.is_active,
            "bm25_weight": self.bm25_weight,
            "pg_fts_weight": self.pg_fts_weight,
            "pg_vec_weight": self.pg_vec_weight,
            "use_reranker": self.use_reranker,
            "reranker_model": self.reranker_model,
            "normalize_scores": self.normalize_scores,
            "metadata_boost": self.metadata_boost,
            "citation_graph_boost": self.citation_graph_boost,
            "top_k": self.top_k,
            "bm25_limit": self.bm25_limit,
            "fts_limit": self.fts_limit,
            "vec_limit": self.vec_limit,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RetrievalProfile":
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        
        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        
        return cls(
            id=data.get("id"),
            profile_name=data["profile_name"],
            display_name=data["display_name"],
            description=data.get("description", ""),
            is_system=data.get("is_system", False),
            is_active=data.get("is_active", True),
            bm25_weight=float(data.get("bm25_weight", 0.0)),
            pg_fts_weight=float(data.get("pg_fts_weight", 0.0)),
            pg_vec_weight=float(data.get("pg_vec_weight", 0.0)),
            use_reranker=data.get("use_reranker", False),
            reranker_model=data.get("reranker_model"),
            normalize_scores=data.get("normalize_scores", True),
            metadata_boost=float(data.get("metadata_boost", 0.0)),
            citation_graph_boost=float(data.get("citation_graph_boost", 0.0)),
            top_k=int(data.get("top_k", 10)),
            bm25_limit=int(data.get("bm25_limit", 30)),
            fts_limit=int(data.get("fts_limit", 30)),
            vec_limit=int(data.get("vec_limit", 30)),
            created_by=data.get("created_by"),
            created_at=created_at,
            updated_at=updated_at,
        )
    
    def validate(self) -> List[str]:
        errors = []
        
        if not self.profile_name or not self.profile_name.strip():
            errors.append("profile_name is required")
        
        if not self.display_name or not self.display_name.strip():
            errors.append("display_name is required")
        
        if self.bm25_weight < 0 or self.bm25_weight > 1:
            errors.append("bm25_weight must be between 0 and 1")
        
        if self.pg_fts_weight < 0 or self.pg_fts_weight > 1:
            errors.append("pg_fts_weight must be between 0 and 1")
        
        if self.pg_vec_weight < 0 or self.pg_vec_weight > 1:
            errors.append("pg_vec_weight must be between 0 and 1")
        
        total_weight = self.bm25_weight + self.pg_fts_weight + self.pg_vec_weight
        if abs(total_weight - 1.0) > 0.01 and total_weight > 0:
            errors.append(f"weights should sum to 1.0 (current sum: {total_weight:.3f})")
        
        if self.top_k < 1:
            errors.append("top_k must be at least 1")
        
        return errors


BUILTIN_PROFILES = {
    "keyword_heavy": RetrievalProfile(
        profile_name="keyword_heavy",
        display_name="Keyword Heavy",
        description="Prioritizes exact keyword matching. Best for queries with specific terminology or technical terms.",
        is_system=True,
        is_active=True,
        bm25_weight=0.50,
        pg_fts_weight=0.30,
        pg_vec_weight=0.20,
        use_reranker=False,
        reranker_model=None,
        normalize_scores=True,
        metadata_boost=0.0,
        citation_graph_boost=0.0,
        top_k=10,
        bm25_limit=30,
        fts_limit=30,
        vec_limit=30,
    ),
    "balanced": RetrievalProfile(
        profile_name="balanced",
        display_name="Balanced",
        description="Balanced approach combining keyword matching and semantic understanding. Good general-purpose profile.",
        is_system=True,
        is_active=True,
        bm25_weight=0.30,
        pg_fts_weight=0.20,
        pg_vec_weight=0.50,
        use_reranker=False,
        reranker_model=None,
        normalize_scores=True,
        metadata_boost=0.0,
        citation_graph_boost=0.0,
        top_k=10,
        bm25_limit=30,
        fts_limit=30,
        vec_limit=30,
    ),
    "conceptual": RetrievalProfile(
        profile_name="conceptual",
        display_name="Conceptual",
        description="Emphasizes semantic similarity. Best for conceptual queries and finding related ideas.",
        is_system=True,
        is_active=True,
        bm25_weight=0.10,
        pg_fts_weight=0.10,
        pg_vec_weight=0.80,
        use_reranker=False,
        reranker_model=None,
        normalize_scores=True,
        metadata_boost=0.0,
        citation_graph_boost=0.0,
        top_k=10,
        bm25_limit=30,
        fts_limit=30,
        vec_limit=30,
    ),
    "academic_evidence": RetrievalProfile(
        profile_name="academic_evidence",
        display_name="Academic Evidence",
        description="Optimized for finding empirical evidence and research findings. Balanced with slight semantic preference.",
        is_system=True,
        is_active=True,
        bm25_weight=0.25,
        pg_fts_weight=0.25,
        pg_vec_weight=0.50,
        use_reranker=False,
        reranker_model=None,
        normalize_scores=True,
        metadata_boost=0.0,
        citation_graph_boost=0.0,
        top_k=10,
        bm25_limit=30,
        fts_limit=30,
        vec_limit=30,
    ),
}


def get_builtin_profile(profile_name: str) -> Optional[RetrievalProfile]:
    return BUILTIN_PROFILES.get(profile_name)


def list_builtin_profiles() -> List[RetrievalProfile]:
    return list(BUILTIN_PROFILES.values())
