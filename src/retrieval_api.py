import uuid
import time
from typing import Any, Dict, List, Optional
from datetime import datetime

from src.supabase_rest import SupabaseRestClient, SupabaseRestError
from src.retrieval_profile_manager import RetrievalProfileManager
from src.retrieval_profiles import RetrievalProfile
from src.benchmark_manager import BenchmarkManager
from src.retrieval_evaluation import BenchmarkQuery, RelevanceLabel, RetrievalEvaluator
from src.retrieval_optimization import GridSearchOptimizer
from src.hybrid_retrieval import HybridRetrievalEngine


class RetrievalAPI:
    def __init__(self, supabase: Optional[SupabaseRestClient] = None):
        self._supabase = supabase
        self._profile_manager = RetrievalProfileManager(supabase)
        self._benchmark_manager = BenchmarkManager(supabase)
        self._evaluator = RetrievalEvaluator()
        self._optimizer = GridSearchOptimizer()
        self._hybrid_engine = HybridRetrievalEngine()
    
    async def list_profiles(self) -> Dict[str, Any]:
        profiles = await self._profile_manager.list_profiles()
        return {
            "status": "success",
            "profiles": [p.to_dict() for p in profiles],
        }
    
    async def get_profile(self, profile_name: str) -> Dict[str, Any]:
        profile = await self._profile_manager.get_profile(profile_name)
        if not profile:
            return {"status": "error", "message": f"Profile '{profile_name}' not found"}
        
        return {
            "status": "success",
            "profile": profile.to_dict(),
        }
    
    async def create_profile(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            profile = RetrievalProfile.from_dict(profile_data)
            created = await self._profile_manager.create_profile(profile)
            
            return {
                "status": "success",
                "profile": created.to_dict(),
                "message": f"Profile '{created.profile_name}' created successfully",
            }
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            return {"status": "error", "message": f"Failed to create profile: {str(e)}"}
    
    async def update_profile(self, profile_name: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        try:
            updated = await self._profile_manager.update_profile(profile_name, updates)
            if not updated:
                return {"status": "error", "message": f"Profile '{profile_name}' not found"}
            
            return {
                "status": "success",
                "profile": updated.to_dict(),
                "message": f"Profile '{profile_name}' updated successfully",
            }
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            return {"status": "error", "message": f"Failed to update profile: {str(e)}"}
    
    async def delete_profile(self, profile_name: str) -> Dict[str, Any]:
        try:
            deleted = await self._profile_manager.delete_profile(profile_name)
            if not deleted:
                return {"status": "error", "message": f"Profile '{profile_name}' not found"}
            
            return {
                "status": "success",
                "message": f"Profile '{profile_name}' deleted successfully",
            }
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            return {"status": "error", "message": f"Failed to delete profile: {str(e)}"}
    
    async def get_project_profile(self, collection: str) -> Dict[str, Any]:
        profile = await self._profile_manager.get_project_profile(collection)
        if not profile:
            return {"status": "error", "message": "No profile found for project"}
        
        return {
            "status": "success",
            "collection": collection,
            "profile": profile.to_dict(),
        }
    
    async def set_project_profile(self, collection: str, profile_name: str) -> Dict[str, Any]:
        try:
            success = await self._profile_manager.set_project_profile(collection, profile_name)
            if not success:
                return {"status": "error", "message": "Failed to set project profile"}
            
            return {
                "status": "success",
                "message": f"Project '{collection}' now uses profile '{profile_name}'",
            }
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            return {"status": "error", "message": f"Failed to set project profile: {str(e)}"}
    
    async def set_project_custom_weights(
        self,
        collection: str,
        bm25_weight: float,
        fts_weight: float,
        vec_weight: float,
        use_reranker: bool = False,
    ) -> Dict[str, Any]:
        try:
            success = await self._profile_manager.set_project_custom_weights(
                collection, bm25_weight, fts_weight, vec_weight, use_reranker
            )
            if not success:
                return {"status": "error", "message": "Failed to set custom weights"}
            
            return {
                "status": "success",
                "message": f"Custom weights set for project '{collection}'",
                "weights": {
                    "bm25": bm25_weight,
                    "fts": fts_weight,
                    "vector": vec_weight,
                },
            }
        except Exception as e:
            return {"status": "error", "message": f"Failed to set custom weights: {str(e)}"}
    
    async def list_benchmark_queries(
        self,
        collection: Optional[str] = None,
        query_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        queries = await self._benchmark_manager.list_benchmark_queries(
            collection=collection,
            query_type=query_type,
        )
        
        return {
            "status": "success",
            "queries": [q.to_dict() for q in queries],
            "count": len(queries),
        }
    
    async def create_benchmark_query(self, query_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if "query_id" not in query_data:
                query_data["query_id"] = f"query_{uuid.uuid4().hex[:12]}"
            
            query = BenchmarkQuery(**query_data)
            created = await self._benchmark_manager.create_benchmark_query(query)
            
            return {
                "status": "success",
                "query": created.to_dict(),
                "message": "Benchmark query created successfully",
            }
        except Exception as e:
            return {"status": "error", "message": f"Failed to create benchmark query: {str(e)}"}
    
    async def bulk_create_benchmark_queries(self, queries: List[Dict[str, Any]]) -> Dict[str, Any]:
        try:
            created = await self._benchmark_manager.bulk_create_benchmark_queries(queries)
            
            return {
                "status": "success",
                "queries": [q.to_dict() for q in created],
                "count": len(created),
                "message": f"Created {len(created)} benchmark queries",
            }
        except Exception as e:
            return {"status": "error", "message": f"Failed to create benchmark queries: {str(e)}"}
    
    async def create_relevance_label(self, label_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            label = RelevanceLabel(**label_data)
            created = await self._benchmark_manager.create_relevance_label(label)
            
            return {
                "status": "success",
                "label": created.to_dict(),
                "message": "Relevance label created successfully",
            }
        except Exception as e:
            return {"status": "error", "message": f"Failed to create relevance label: {str(e)}"}
    
    async def bulk_create_relevance_labels(self, labels: List[Dict[str, Any]]) -> Dict[str, Any]:
        try:
            created = await self._benchmark_manager.bulk_create_relevance_labels(labels)
            
            return {
                "status": "success",
                "labels": [l.to_dict() for l in created],
                "count": len(created),
                "message": f"Created {len(created)} relevance labels",
            }
        except Exception as e:
            return {"status": "error", "message": f"Failed to create relevance labels: {str(e)}"}
    
    async def get_labels_for_query(self, query_id: str) -> Dict[str, Any]:
        labels = await self._benchmark_manager.get_labels_for_query(query_id)
        
        return {
            "status": "success",
            "query_id": query_id,
            "labels": [l.to_dict() for l in labels],
            "count": len(labels),
        }
    
    async def create_annotation_session(self, collection: str, annotator: str) -> Dict[str, Any]:
        try:
            session_id = await self._benchmark_manager.create_annotation_session(collection, annotator)
            
            return {
                "status": "success",
                "session_id": session_id,
                "collection": collection,
                "annotator": annotator,
                "message": "Annotation session created",
            }
        except Exception as e:
            return {"status": "error", "message": f"Failed to create annotation session: {str(e)}"}
    
    async def save_retrieval_run(
        self,
        collection: str,
        profile: RetrievalProfile,
        metrics: Dict[str, Any],
        run_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self._supabase:
            return {"status": "error", "message": "Supabase not configured"}
        
        try:
            run_id = f"run_{uuid.uuid4().hex[:12]}"
            
            row = {
                "run_id": run_id,
                "run_name": run_name or f"Run {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
                "collection": collection,
                "profile_id": profile.id,
                "profile_name": profile.profile_name,
                "bm25_weight": profile.bm25_weight,
                "pg_fts_weight": profile.pg_fts_weight,
                "pg_vec_weight": profile.pg_vec_weight,
                "use_reranker": profile.use_reranker,
                "reranker_model": profile.reranker_model,
                "normalize_scores": profile.normalize_scores,
                "top_k": profile.top_k,
                "precision_at_5": metrics.get("avg_precision_at_5"),
                "precision_at_10": metrics.get("avg_precision_at_10"),
                "recall_at_5": metrics.get("avg_recall_at_5"),
                "recall_at_10": metrics.get("avg_recall_at_10"),
                "recall_at_20": metrics.get("avg_recall_at_20"),
                "ndcg_at_5": metrics.get("avg_ndcg_at_5"),
                "ndcg_at_10": metrics.get("avg_ndcg_at_10"),
                "mrr": metrics.get("avg_mrr"),
                "map_score": metrics.get("avg_map"),
                "num_queries": metrics.get("num_queries"),
                "metrics_by_query_type": metrics.get("by_query_type"),
            }
            
            result = await self._supabase.insert("RetrievalRuns", rows=[row])
            
            return {
                "status": "success",
                "run_id": run_id,
                "message": "Retrieval run saved successfully",
            }
        except Exception as e:
            return {"status": "error", "message": f"Failed to save retrieval run: {str(e)}"}
    
    async def list_retrieval_runs(self, collection: Optional[str] = None) -> Dict[str, Any]:
        if not self._supabase:
            return {"status": "error", "message": "Supabase not configured"}
        
        try:
            filters = {}
            if collection:
                filters["collection"] = f"eq.{collection}"
            
            rows = await self._supabase.select(
                "RetrievalRuns",
                filters=filters,
                order="created_at.desc",
            )
            
            return {
                "status": "success",
                "runs": rows,
                "count": len(rows),
            }
        except Exception as e:
            return {"status": "error", "message": f"Failed to list retrieval runs: {str(e)}"}
    
    async def get_best_run(self, collection: str, metric_name: str = "ndcg_at_10") -> Dict[str, Any]:
        if not self._supabase:
            return {"status": "error", "message": "Supabase not configured"}
        
        try:
            rows = await self._supabase.select(
                "RetrievalRuns",
                filters={"collection": f"eq.{collection}"},
                order=f"{metric_name}.desc",
                limit=1,
            )
            
            if not rows:
                return {"status": "error", "message": "No runs found for this collection"}
            
            return {
                "status": "success",
                "best_run": rows[0],
                "metric": metric_name,
            }
        except Exception as e:
            return {"status": "error", "message": f"Failed to get best run: {str(e)}"}
    
    async def save_optimization_result(
        self,
        collection: str,
        optimization_type: str,
        best_run_id: str,
        best_profile: RetrievalProfile,
        best_metric_value: float,
        baseline_metric_value: float,
        metric_name: str,
        num_configurations: int,
        duration_seconds: float,
        all_run_ids: List[str],
    ) -> Dict[str, Any]:
        if not self._supabase:
            return {"status": "error", "message": "Supabase not configured"}
        
        try:
            optimization_id = f"opt_{uuid.uuid4().hex[:12]}"
            improvement_pct = ((best_metric_value - baseline_metric_value) / baseline_metric_value * 100) if baseline_metric_value > 0 else 0.0
            
            row = {
                "optimization_id": optimization_id,
                "collection": collection,
                "optimization_type": optimization_type,
                "best_run_id": best_run_id,
                "best_profile_id": best_profile.id,
                "best_metric_name": metric_name,
                "best_metric_value": best_metric_value,
                "baseline_metric_value": baseline_metric_value,
                "improvement_pct": improvement_pct,
                "run_ids": all_run_ids,
                "num_configurations_tested": num_configurations,
                "total_duration_seconds": duration_seconds,
                "status": "completed",
                "completed_at": datetime.utcnow().isoformat(),
            }
            
            result = await self._supabase.insert("OptimizationHistory", rows=[row])
            
            return {
                "status": "success",
                "optimization_id": optimization_id,
                "improvement_pct": improvement_pct,
                "message": "Optimization result saved successfully",
            }
        except Exception as e:
            return {"status": "error", "message": f"Failed to save optimization result: {str(e)}"}
    
    async def list_optimizations(self, collection: Optional[str] = None) -> Dict[str, Any]:
        if not self._supabase:
            return {"status": "error", "message": "Supabase not configured"}
        
        try:
            filters = {}
            if collection:
                filters["collection"] = f"eq.{collection}"
            
            rows = await self._supabase.select(
                "OptimizationHistory",
                filters=filters,
                order="created_at.desc",
            )
            
            return {
                "status": "success",
                "optimizations": rows,
                "count": len(rows),
            }
        except Exception as e:
            return {"status": "error", "message": f"Failed to list optimizations: {str(e)}"}
