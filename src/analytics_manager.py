import logging
from typing import Any, Dict, List, Optional
from collections import defaultdict

from src.supabase_rest import SupabaseRestClient, SupabaseRestError

logger = logging.getLogger(__name__)


class AnalyticsManager:
    """Provides analytics and insights on retrieval performance and document usage"""
    
    def __init__(self, supabase: SupabaseRestClient):
        self._supabase = supabase
    
    async def get_document_analytics(
        self,
        collection: Optional[str] = None,
        user_id: str = "default_user",
        limit: int = 100
    ) -> Dict[str, Any]:
        """Get document performance analytics"""
        try:
            filters = {"user_id": f"eq.{user_id}", "is_active": "eq.true"}
            if collection:
                filters["collection"] = f"eq.{collection}"
            
            # Get from materialized view
            docs = await self._supabase.select(
                "DocumentPerformanceSummary",
                select="*",
                filters=filters,
                limit=limit
            )
            
            # Fallback to Documents table if materialized view is empty
            if not docs:
                logger.info("DocumentPerformanceSummary is empty, falling back to Documents table")
                doc_filters = {"user_id": f"eq.{user_id}", "is_active": "eq.true"}
                if collection:
                    doc_filters["collection"] = f"eq.{collection}"
                
                basic_docs = await self._supabase.select(
                    "Documents",
                    select="id,title,collection,pdf_attached,ingestion_status,metadata_complete",
                    filters=doc_filters,
                    limit=limit
                )
                
                # Convert to format expected by analytics
                docs = [{
                    **doc,
                    "total_retrievals": 0,
                    "total_citations": 0,
                    "avg_overall_score": None
                } for doc in (basic_docs or [])]
            
            # Calculate summary statistics
            total_docs = len(docs)
            docs_with_retrievals = sum(1 for d in docs if d.get("total_retrievals", 0) > 0)
            docs_with_citations = sum(1 for d in docs if d.get("total_citations", 0) > 0)
            docs_unused = sum(1 for d in docs if d.get("total_retrievals", 0) == 0)
            
            # Most retrieved
            most_retrieved = sorted(docs, key=lambda d: d.get("total_retrievals", 0), reverse=True)[:10]
            
            # Most cited
            most_cited = sorted(docs, key=lambda d: d.get("total_citations", 0), reverse=True)[:10]
            
            # Highest rated
            rated_docs = [d for d in docs if d.get("avg_overall_score") is not None]
            highest_rated = sorted(rated_docs, key=lambda d: d.get("avg_overall_score", 0), reverse=True)[:10]
            
            # Retrieved but never cited (potential low-quality sources)
            retrieved_not_cited = [
                d for d in docs 
                if d.get("total_retrievals", 0) > 0 and d.get("total_citations", 0) == 0
            ]
            
            # Documents needing attention
            needs_attention = [
                d for d in docs
                if not d.get("pdf_attached") or 
                   d.get("ingestion_status") == "failed" or
                   not d.get("metadata_complete")
            ]
            
            return {
                "status": "success",
                "analytics": {
                    "summary": {
                        "total_documents": total_docs,
                        "documents_with_retrievals": docs_with_retrievals,
                        "documents_with_citations": docs_with_citations,
                        "documents_unused": docs_unused,
                        "documents_needing_attention": len(needs_attention)
                    },
                    "most_retrieved": most_retrieved,
                    "most_cited": most_cited,
                    "highest_rated": highest_rated,
                    "retrieved_but_not_cited": retrieved_not_cited[:10],
                    "needs_attention": needs_attention[:10]
                }
            }
            
        except SupabaseRestError as e:
            logger.error(f"Error getting document analytics: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_retrieval_mode_analytics(
        self,
        collection: Optional[str] = None,
        use_case_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze performance by retrieval mode"""
        try:
            filters: Dict[str, str] = {}
            if collection:
                filters["collection"] = f"eq.{collection}"
            if use_case_type:
                filters["use_case_type"] = f"eq.{use_case_type}"
            
            # Get all query runs
            query_runs = await self._supabase.select(
                "QueryRuns",
                select="*",
                filters=filters
            )
            
            # Group by retrieval mode
            mode_stats = defaultdict(lambda: {
                "count": 0,
                "total_response_time": 0,
                "total_retrieval_time": 0,
                "evaluations": []
            })
            
            for qr in query_runs:
                mode = qr.get("retrieval_mode", "unknown")
                mode_stats[mode]["count"] += 1
                
                if qr.get("response_time_ms"):
                    mode_stats[mode]["total_response_time"] += qr["response_time_ms"]
                if qr.get("retrieval_time_ms"):
                    mode_stats[mode]["total_retrieval_time"] += qr["retrieval_time_ms"]
                
                # Get evaluations for this query run
                evals = await self._supabase.select(
                    "QueryRunEvaluations",
                    select="*",
                    filters={"query_run_id": f"eq.{qr['id']}"}
                )
                mode_stats[mode]["evaluations"].extend(evals)
            
            # Calculate averages
            results = {}
            for mode, stats in mode_stats.items():
                count = stats["count"]
                evals = stats["evaluations"]
                
                avg_overall = None
                avg_accuracy = None
                if evals:
                    overall_scores = [e["overall_score"] for e in evals if e.get("overall_score")]
                    accuracy_scores = [e["accuracy_score"] for e in evals if e.get("accuracy_score")]
                    avg_overall = sum(overall_scores) / len(overall_scores) if overall_scores else None
                    avg_accuracy = sum(accuracy_scores) / len(accuracy_scores) if accuracy_scores else None
                
                results[mode] = {
                    "query_count": count,
                    "avg_response_time_ms": stats["total_response_time"] / count if count > 0 else None,
                    "avg_retrieval_time_ms": stats["total_retrieval_time"] / count if count > 0 else None,
                    "evaluation_count": len(evals),
                    "avg_overall_score": avg_overall,
                    "avg_accuracy_score": avg_accuracy
                }
            
            return {"status": "success", "analytics": results}
            
        except SupabaseRestError as e:
            logger.error(f"Error getting retrieval mode analytics: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_model_comparison(
        self,
        collection: Optional[str] = None
    ) -> Dict[str, Any]:
        """Compare LLM model performance"""
        try:
            filters: Dict[str, str] = {}
            if collection:
                filters["collection"] = f"eq.{collection}"
            
            # Get all query runs
            query_runs = await self._supabase.select(
                "QueryRuns",
                select="*",
                filters=filters
            )
            
            # Group by LLM model
            model_stats = defaultdict(lambda: {
                "count": 0,
                "total_response_time": 0,
                "total_llm_time": 0,
                "total_tokens_in": 0,
                "total_tokens_out": 0,
                "total_cost": 0,
                "evaluations": []
            })
            
            for qr in query_runs:
                model = qr.get("llm_model", "unknown")
                model_stats[model]["count"] += 1
                
                if qr.get("response_time_ms"):
                    model_stats[model]["total_response_time"] += qr["response_time_ms"]
                if qr.get("llm_time_ms"):
                    model_stats[model]["total_llm_time"] += qr["llm_time_ms"]
                if qr.get("token_input"):
                    model_stats[model]["total_tokens_in"] += qr["token_input"]
                if qr.get("token_output"):
                    model_stats[model]["total_tokens_out"] += qr["token_output"]
                if qr.get("estimated_cost"):
                    model_stats[model]["total_cost"] += qr["estimated_cost"]
                
                # Get evaluations
                evals = await self._supabase.select(
                    "QueryRunEvaluations",
                    select="*",
                    filters={"query_run_id": f"eq.{qr['id']}"}
                )
                model_stats[model]["evaluations"].extend(evals)
            
            # Calculate averages
            results = {}
            for model, stats in model_stats.items():
                count = stats["count"]
                evals = stats["evaluations"]
                
                avg_scores = {}
                if evals:
                    for score_field in ["overall_score", "accuracy_score", "relevance_score", "clarity_score"]:
                        scores = [e[score_field] for e in evals if e.get(score_field)]
                        avg_scores[f"avg_{score_field}"] = sum(scores) / len(scores) if scores else None
                
                results[model] = {
                    "query_count": count,
                    "avg_response_time_ms": stats["total_response_time"] / count if count > 0 else None,
                    "avg_llm_time_ms": stats["total_llm_time"] / count if count > 0 else None,
                    "avg_tokens_in": stats["total_tokens_in"] / count if count > 0 else None,
                    "avg_tokens_out": stats["total_tokens_out"] / count if count > 0 else None,
                    "total_cost": stats["total_cost"],
                    "avg_cost_per_query": stats["total_cost"] / count if count > 0 else None,
                    "evaluation_count": len(evals),
                    **avg_scores
                }
            
            return {"status": "success", "analytics": results}
            
        except SupabaseRestError as e:
            logger.error(f"Error getting model comparison: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_use_case_analytics(
        self,
        collection: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze performance by use case type"""
        try:
            filters: Dict[str, str] = {}
            if collection:
                filters["collection"] = f"eq.{collection}"
            
            # Get all query runs
            query_runs = await self._supabase.select(
                "QueryRuns",
                select="*",
                filters=filters
            )
            
            # Group by use case type
            use_case_stats = defaultdict(lambda: {
                "count": 0,
                "retrieval_modes": defaultdict(int),
                "evaluations": []
            })
            
            for qr in query_runs:
                use_case = qr.get("use_case_type", "unspecified")
                use_case_stats[use_case]["count"] += 1
                
                if qr.get("retrieval_mode"):
                    use_case_stats[use_case]["retrieval_modes"][qr["retrieval_mode"]] += 1
                
                # Get evaluations
                evals = await self._supabase.select(
                    "QueryRunEvaluations",
                    select="*",
                    filters={"query_run_id": f"eq.{qr['id']}"}
                )
                use_case_stats[use_case]["evaluations"].extend(evals)
            
            # Calculate statistics
            results = {}
            for use_case, stats in use_case_stats.items():
                evals = stats["evaluations"]
                
                avg_overall = None
                if evals:
                    overall_scores = [e["overall_score"] for e in evals if e.get("overall_score")]
                    avg_overall = sum(overall_scores) / len(overall_scores) if overall_scores else None
                
                # Find most common retrieval mode
                most_common_mode = max(stats["retrieval_modes"].items(), key=lambda x: x[1])[0] if stats["retrieval_modes"] else None
                
                results[use_case] = {
                    "query_count": stats["count"],
                    "evaluation_count": len(evals),
                    "avg_overall_score": avg_overall,
                    "most_common_retrieval_mode": most_common_mode,
                    "retrieval_mode_distribution": dict(stats["retrieval_modes"])
                }
            
            return {"status": "success", "analytics": results}
            
        except SupabaseRestError as e:
            logger.error(f"Error getting use case analytics: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_time_series_data(
        self,
        collection: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get time-series performance data"""
        try:
            filters: Dict[str, str] = {}
            if collection:
                filters["collection"] = f"eq.{collection}"
            
            # Get query runs from last N days
            query_runs = await self._supabase.select(
                "QueryRuns",
                select="*",
                filters=filters,
                order="created_at.desc"
            )
            
            # Group by date
            daily_stats = defaultdict(lambda: {
                "query_count": 0,
                "avg_response_time": 0,
                "evaluations": []
            })
            
            for qr in query_runs:
                created_at = qr.get("created_at", "")
                date = created_at.split("T")[0] if created_at else "unknown"
                
                daily_stats[date]["query_count"] += 1
                if qr.get("response_time_ms"):
                    daily_stats[date]["avg_response_time"] += qr["response_time_ms"]
                
                # Get evaluations
                evals = await self._supabase.select(
                    "QueryRunEvaluations",
                    select="*",
                    filters={"query_run_id": f"eq.{qr['id']}"}
                )
                daily_stats[date]["evaluations"].extend(evals)
            
            # Calculate daily averages
            results = []
            for date, stats in sorted(daily_stats.items()):
                count = stats["query_count"]
                evals = stats["evaluations"]
                
                avg_score = None
                if evals:
                    scores = [e["overall_score"] for e in evals if e.get("overall_score")]
                    avg_score = sum(scores) / len(scores) if scores else None
                
                results.append({
                    "date": date,
                    "query_count": count,
                    "avg_response_time_ms": stats["avg_response_time"] / count if count > 0 else None,
                    "evaluation_count": len(evals),
                    "avg_overall_score": avg_score
                })
            
            return {"status": "success", "time_series": results}
            
        except SupabaseRestError as e:
            logger.error(f"Error getting time series data: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_dashboard_summary(
        self,
        collection: Optional[str] = None,
        user_id: str = "default_user"
    ) -> Dict[str, Any]:
        """Get comprehensive dashboard summary"""
        try:
            # Get document stats
            doc_analytics = await self.get_document_analytics(collection, user_id, limit=1000)
            
            # Get recent query runs
            filters: Dict[str, str] = {"user_id": f"eq.{user_id}"}
            if collection:
                filters["collection"] = f"eq.{collection}"
            
            recent_runs = await self._supabase.select(
                "QueryRuns",
                select="*",
                filters=filters,
                order="created_at.desc",
                limit=100
            )
            
            # Get recent evaluations
            recent_evals = await self._supabase.select(
                "QueryRunEvaluations",
                select="*",
                order="created_at.desc",
                limit=50
            )
            
            # Calculate overall stats
            total_queries = len(recent_runs)
            total_evaluations = len(recent_evals)
            
            avg_response_time = None
            if recent_runs:
                response_times = [qr["response_time_ms"] for qr in recent_runs if qr.get("response_time_ms")]
                avg_response_time = sum(response_times) / len(response_times) if response_times else None
            
            avg_overall_score = None
            if recent_evals:
                scores = [e["overall_score"] for e in recent_evals if e.get("overall_score")]
                avg_overall_score = sum(scores) / len(scores) if scores else None
            
            return {
                "status": "success",
                "summary": {
                    "documents": doc_analytics.get("analytics", {}).get("summary", {}),
                    "queries": {
                        "total_recent_queries": total_queries,
                        "total_evaluations": total_evaluations,
                        "avg_response_time_ms": avg_response_time,
                        "avg_overall_score": avg_overall_score
                    },
                    "top_documents": doc_analytics.get("analytics", {}).get("most_cited", [])[:5],
                    "recent_query_runs": recent_runs[:10]
                }
            }
            
        except SupabaseRestError as e:
            logger.error(f"Error getting dashboard summary: {e}")
            return {"status": "error", "message": str(e)}
