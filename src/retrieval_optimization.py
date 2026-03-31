import itertools
import uuid
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from src.retrieval_profiles import RetrievalProfile
from src.retrieval_evaluation import RetrievalEvaluator


class GridSearchOptimizer:
    def __init__(self):
        self.evaluator = RetrievalEvaluator()
    
    def generate_weight_combinations(
        self,
        bm25_range: List[float],
        fts_range: List[float],
        vec_range: List[float],
        normalize: bool = True,
    ) -> List[Tuple[float, float, float]]:
        combinations = []
        
        for bm25_w in bm25_range:
            for fts_w in fts_range:
                for vec_w in vec_range:
                    if normalize:
                        total = bm25_w + fts_w + vec_w
                        if total > 0:
                            combinations.append((
                                bm25_w / total,
                                fts_w / total,
                                vec_w / total,
                            ))
                    else:
                        combinations.append((bm25_w, fts_w, vec_w))
        
        seen = set()
        unique_combinations = []
        for combo in combinations:
            rounded = tuple(round(w, 3) for w in combo)
            if rounded not in seen:
                seen.add(rounded)
                unique_combinations.append(combo)
        
        return unique_combinations
    
    def create_profile_from_weights(
        self,
        bm25_weight: float,
        fts_weight: float,
        vec_weight: float,
        base_profile: Optional[RetrievalProfile] = None,
        profile_name: Optional[str] = None,
    ) -> RetrievalProfile:
        if base_profile:
            profile = RetrievalProfile(
                profile_name=profile_name or f"grid_search_{uuid.uuid4().hex[:8]}",
                display_name=f"Grid Search ({bm25_weight:.2f}, {fts_weight:.2f}, {vec_weight:.2f})",
                description=f"BM25: {bm25_weight:.2f}, FTS: {fts_weight:.2f}, Vector: {vec_weight:.2f}",
                is_system=False,
                is_active=True,
                bm25_weight=bm25_weight,
                pg_fts_weight=fts_weight,
                pg_vec_weight=vec_weight,
                use_reranker=base_profile.use_reranker,
                reranker_model=base_profile.reranker_model,
                normalize_scores=base_profile.normalize_scores,
                metadata_boost=base_profile.metadata_boost,
                citation_graph_boost=base_profile.citation_graph_boost,
                top_k=base_profile.top_k,
                bm25_limit=base_profile.bm25_limit,
                fts_limit=base_profile.fts_limit,
                vec_limit=base_profile.vec_limit,
            )
        else:
            profile = RetrievalProfile(
                profile_name=profile_name or f"grid_search_{uuid.uuid4().hex[:8]}",
                display_name=f"Grid Search ({bm25_weight:.2f}, {fts_weight:.2f}, {vec_weight:.2f})",
                description=f"BM25: {bm25_weight:.2f}, FTS: {fts_weight:.2f}, Vector: {vec_weight:.2f}",
                is_system=False,
                is_active=True,
                bm25_weight=bm25_weight,
                pg_fts_weight=fts_weight,
                pg_vec_weight=vec_weight,
                use_reranker=False,
                reranker_model=None,
                normalize_scores=True,
                metadata_boost=0.0,
                citation_graph_boost=0.0,
                top_k=10,
                bm25_limit=30,
                fts_limit=30,
                vec_limit=30,
            )
        
        return profile
    
    def optimize_weights(
        self,
        retrieval_function: Any,
        benchmark_queries: List[Any],
        labels_by_query: Dict[str, List[Any]],
        bm25_range: Optional[List[float]] = None,
        fts_range: Optional[List[float]] = None,
        vec_range: Optional[List[float]] = None,
        metric_name: str = "ndcg_at_10",
        base_profile: Optional[RetrievalProfile] = None,
    ) -> Tuple[RetrievalProfile, Dict[str, Any], List[Dict[str, Any]]]:
        if bm25_range is None:
            bm25_range = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
        if fts_range is None:
            fts_range = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
        if vec_range is None:
            vec_range = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
        
        weight_combinations = self.generate_weight_combinations(
            bm25_range, fts_range, vec_range, normalize=True
        )
        
        all_results = []
        best_profile = None
        best_metrics = None
        best_score = -1.0
        
        for bm25_w, fts_w, vec_w in weight_combinations:
            profile = self.create_profile_from_weights(
                bm25_w, fts_w, vec_w, base_profile=base_profile
            )
            
            results_by_query = {}
            for query in benchmark_queries:
                query_id = query.query_id
                query_text = query.query_text
                
                retrieved = retrieval_function(query_text, profile)
                results_by_query[query_id] = retrieved
            
            metrics = self.evaluator.evaluate_multiple_queries(
                results_by_query, labels_by_query
            )
            
            result = {
                "profile": profile,
                "bm25_weight": bm25_w,
                "fts_weight": fts_w,
                "vec_weight": vec_w,
                "metrics": metrics,
                "score": metrics.get(f"avg_{metric_name}", 0.0),
            }
            all_results.append(result)
            
            if result["score"] > best_score:
                best_score = result["score"]
                best_profile = profile
                best_metrics = metrics
        
        all_results.sort(key=lambda x: x["score"], reverse=True)
        
        return best_profile, best_metrics, all_results
    
    def optimize_by_query_type(
        self,
        retrieval_function: Any,
        benchmark_queries: List[Any],
        labels_by_query: Dict[str, List[Any]],
        query_types: List[str],
        bm25_range: Optional[List[float]] = None,
        fts_range: Optional[List[float]] = None,
        vec_range: Optional[List[float]] = None,
        metric_name: str = "ndcg_at_10",
        base_profile: Optional[RetrievalProfile] = None,
    ) -> Dict[str, Tuple[RetrievalProfile, Dict[str, Any]]]:
        results_by_type = {}
        
        for query_type in query_types:
            type_queries = [q for q in benchmark_queries if q.query_type == query_type]
            if not type_queries:
                continue
            
            type_labels = {
                qid: labels
                for qid, labels in labels_by_query.items()
                if any(q.query_id == qid and q.query_type == query_type for q in type_queries)
            }
            
            best_profile, best_metrics, _ = self.optimize_weights(
                retrieval_function=retrieval_function,
                benchmark_queries=type_queries,
                labels_by_query=type_labels,
                bm25_range=bm25_range,
                fts_range=fts_range,
                vec_range=vec_range,
                metric_name=metric_name,
                base_profile=base_profile,
            )
            
            results_by_type[query_type] = (best_profile, best_metrics)
        
        return results_by_type


class OptimizationRecommender:
    def __init__(self):
        pass
    
    def recommend_profile_for_query(
        self,
        query_text: str,
        query_type: Optional[str],
        profiles_by_type: Dict[str, RetrievalProfile],
        default_profile: RetrievalProfile,
    ) -> RetrievalProfile:
        if query_type and query_type in profiles_by_type:
            return profiles_by_type[query_type]
        
        query_lower = query_text.lower()
        
        if any(word in query_lower for word in ["define", "definition", "what is", "meaning of"]):
            if "definitional" in profiles_by_type:
                return profiles_by_type["definitional"]
        
        if any(word in query_lower for word in ["study", "research", "evidence", "finding", "result"]):
            if "empirical_evidence" in profiles_by_type:
                return profiles_by_type["empirical_evidence"]
        
        if any(word in query_lower for word in ["critique", "limitation", "weakness", "problem"]):
            if "critique" in profiles_by_type:
                return profiles_by_type["critique"]
        
        if any(word in query_lower for word in ["method", "methodology", "approach", "technique"]):
            if "methodological" in profiles_by_type:
                return profiles_by_type["methodological"]
        
        return default_profile
    
    def generate_benchmark_from_section_headings(
        self,
        document_sections: List[Dict[str, str]],
        collection: str,
    ) -> List[Dict[str, Any]]:
        benchmarks = []
        
        section_to_type = {
            "introduction": "background",
            "background": "background",
            "literature review": "synthesis",
            "methodology": "methodological",
            "methods": "methodological",
            "results": "empirical_evidence",
            "discussion": "synthesis",
            "conclusion": "synthesis",
            "limitations": "critique",
        }
        
        for idx, section in enumerate(document_sections):
            heading = section.get("heading", "").strip()
            if not heading:
                continue
            
            query_text = f"What does the literature say about {heading.lower()}?"
            
            section_lower = heading.lower()
            query_type = "synthesis"
            for key, qtype in section_to_type.items():
                if key in section_lower:
                    query_type = qtype
                    break
            
            benchmarks.append({
                "query_id": f"section_{idx}_{uuid.uuid4().hex[:8]}",
                "collection": collection,
                "query_text": query_text,
                "query_type": query_type,
                "section_goal": heading,
                "source": "section_heading",
                "source_metadata": {"heading": heading, "section_index": idx},
            })
        
        return benchmarks
