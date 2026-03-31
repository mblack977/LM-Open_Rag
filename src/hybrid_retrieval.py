import math
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict

from src.retrieval_profiles import RetrievalProfile


class RetrievalCandidate:
    def __init__(
        self,
        doc_id: str,
        chunk_index: int,
        text: str,
        source: str,
        raw_score: float,
        normalized_score: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.doc_id = doc_id
        self.chunk_index = chunk_index
        self.text = text
        self.source = source
        self.raw_score = raw_score
        self.normalized_score = normalized_score
        self.metadata = metadata or {}
        self.final_score = 0.0
        self.sources = [source]
    
    def get_key(self) -> Tuple[str, int]:
        return (self.doc_id, self.chunk_index)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "chunk_index": self.chunk_index,
            "text": self.text,
            "source": self.source,
            "sources": self.sources,
            "raw_score": self.raw_score,
            "normalized_score": self.normalized_score,
            "final_score": self.final_score,
            **self.metadata,
        }


class HybridRetrievalEngine:
    def __init__(self):
        pass
    
    def normalize_scores(self, candidates: List[RetrievalCandidate], method: str = "minmax") -> None:
        if not candidates:
            return
        
        if method == "minmax":
            scores = [c.raw_score for c in candidates]
            min_score = min(scores)
            max_score = max(scores)
            
            if max_score - min_score < 1e-9:
                for c in candidates:
                    c.normalized_score = 1.0
            else:
                for c in candidates:
                    c.normalized_score = (c.raw_score - min_score) / (max_score - min_score)
        
        elif method == "zscore":
            scores = [c.raw_score for c in candidates]
            mean = sum(scores) / len(scores)
            variance = sum((s - mean) ** 2 for s in scores) / len(scores)
            std = math.sqrt(variance) if variance > 0 else 1.0
            
            for c in candidates:
                z = (c.raw_score - mean) / std if std > 0 else 0.0
                c.normalized_score = 1.0 / (1.0 + math.exp(-z))
        
        else:
            for c in candidates:
                c.normalized_score = c.raw_score
    
    def merge_candidates(
        self,
        bm25_candidates: List[RetrievalCandidate],
        fts_candidates: List[RetrievalCandidate],
        vec_candidates: List[RetrievalCandidate],
        profile: RetrievalProfile,
    ) -> List[RetrievalCandidate]:
        if profile.normalize_scores:
            self.normalize_scores(bm25_candidates, method="minmax")
            self.normalize_scores(fts_candidates, method="minmax")
            self.normalize_scores(vec_candidates, method="minmax")
        else:
            for c in bm25_candidates:
                c.normalized_score = c.raw_score
            for c in fts_candidates:
                c.normalized_score = c.raw_score
            for c in vec_candidates:
                c.normalized_score = c.raw_score
        
        merged: Dict[Tuple[str, int], RetrievalCandidate] = {}
        
        for c in bm25_candidates:
            key = c.get_key()
            if key not in merged:
                merged[key] = c
                merged[key].final_score = c.normalized_score * profile.bm25_weight
            else:
                merged[key].final_score += c.normalized_score * profile.bm25_weight
                if "bm25" not in merged[key].sources:
                    merged[key].sources.append("bm25")
        
        for c in fts_candidates:
            key = c.get_key()
            if key not in merged:
                merged[key] = c
                merged[key].final_score = c.normalized_score * profile.pg_fts_weight
            else:
                merged[key].final_score += c.normalized_score * profile.pg_fts_weight
                if "fts" not in merged[key].sources:
                    merged[key].sources.append("fts")
        
        for c in vec_candidates:
            key = c.get_key()
            if key not in merged:
                merged[key] = c
                merged[key].final_score = c.normalized_score * profile.pg_vec_weight
            else:
                merged[key].final_score += c.normalized_score * profile.pg_vec_weight
                if "vector" not in merged[key].sources:
                    merged[key].sources.append("vector")
        
        if profile.metadata_boost > 0:
            for c in merged.values():
                if c.metadata.get("title") or c.metadata.get("authors"):
                    c.final_score *= (1.0 + profile.metadata_boost)
        
        result = list(merged.values())
        result.sort(key=lambda x: x.final_score, reverse=True)
        
        return result
    
    def reciprocal_rank_fusion(
        self,
        bm25_candidates: List[RetrievalCandidate],
        fts_candidates: List[RetrievalCandidate],
        vec_candidates: List[RetrievalCandidate],
        k: int = 60,
    ) -> List[RetrievalCandidate]:
        merged: Dict[Tuple[str, int], RetrievalCandidate] = {}
        
        def add_list(candidates: List[RetrievalCandidate], source_label: str) -> None:
            for rank, c in enumerate(candidates):
                key = c.get_key()
                rrf_score = 1.0 / (k + rank + 1)
                
                if key not in merged:
                    merged[key] = c
                    merged[key].final_score = rrf_score
                    merged[key].sources = [source_label]
                else:
                    merged[key].final_score += rrf_score
                    if source_label not in merged[key].sources:
                        merged[key].sources.append(source_label)
        
        add_list(bm25_candidates, "bm25")
        add_list(fts_candidates, "fts")
        add_list(vec_candidates, "vector")
        
        result = list(merged.values())
        result.sort(key=lambda x: x.final_score, reverse=True)
        
        return result
    
    def retrieve_with_profile(
        self,
        bm25_results: List[Dict[str, Any]],
        fts_results: List[Dict[str, Any]],
        vec_results: List[Dict[str, Any]],
        profile: RetrievalProfile,
        use_rrf: bool = False,
    ) -> List[Dict[str, Any]]:
        bm25_candidates = [
            RetrievalCandidate(
                doc_id=r.get("doc_id", ""),
                chunk_index=r.get("chunk_index", -1),
                text=r.get("text", ""),
                source="bm25",
                raw_score=r.get("score", 0.0),
                metadata={
                    "filename": r.get("filename"),
                    "title": r.get("title"),
                    "authors": r.get("authors"),
                    "tags": r.get("tags"),
                },
            )
            for r in bm25_results
        ]
        
        fts_candidates = [
            RetrievalCandidate(
                doc_id=r.get("doc_id", ""),
                chunk_index=r.get("chunk_index", -1),
                text=r.get("text", ""),
                source="fts",
                raw_score=r.get("rank", 0.0),
                metadata={
                    "filename": r.get("filename"),
                    "title": r.get("title"),
                    "authors": r.get("authors"),
                    "tags": r.get("tags"),
                },
            )
            for r in fts_results
        ]
        
        vec_candidates = [
            RetrievalCandidate(
                doc_id=r.get("doc_id", ""),
                chunk_index=r.get("chunk_index", -1),
                text=r.get("text", ""),
                source="vector",
                raw_score=r.get("score", 0.0),
                metadata={
                    "filename": r.get("filename"),
                    "title": r.get("title"),
                    "authors": r.get("authors"),
                    "tags": r.get("tags"),
                },
            )
            for r in vec_results
        ]
        
        if use_rrf:
            merged = self.reciprocal_rank_fusion(bm25_candidates, fts_candidates, vec_candidates)
        else:
            merged = self.merge_candidates(bm25_candidates, fts_candidates, vec_candidates, profile)
        
        top_k = profile.top_k
        return [c.to_dict() for c in merged[:top_k]]
    
    def compute_bm25_score(
        self,
        query_terms: List[str],
        doc_terms: List[str],
        doc_freq: Dict[str, int],
        total_docs: int,
        avg_doc_length: float,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> float:
        score = 0.0
        doc_length = len(doc_terms)
        doc_term_freq = defaultdict(int)
        for term in doc_terms:
            doc_term_freq[term] += 1
        
        for term in query_terms:
            if term not in doc_term_freq:
                continue
            
            tf = doc_term_freq[term]
            df = doc_freq.get(term, 1)
            idf = math.log((total_docs - df + 0.5) / (df + 0.5) + 1.0)
            
            norm_tf = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (doc_length / avg_doc_length)))
            
            score += idf * norm_tf
        
        return score
