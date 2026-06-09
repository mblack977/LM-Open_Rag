import logging
from typing import Any, Dict, List, Optional

from src.supabase_rest import SupabaseRestClient, SupabaseRestError

logger = logging.getLogger(__name__)


class EvaluationManager:
    """Manages query run evaluations and quality scoring"""
    
    def __init__(self, supabase: SupabaseRestClient):
        self._supabase = supabase
    
    async def create_evaluation(
        self,
        query_run_id: str,
        evaluator_user_id: str = "default_user",
        overall_score: Optional[int] = None,
        accuracy_score: Optional[int] = None,
        relevance_score: Optional[int] = None,
        completeness_score: Optional[int] = None,
        clarity_score: Optional[int] = None,
        source_usefulness_score: Optional[int] = None,
        citation_quality_score: Optional[int] = None,
        hallucination_flag: bool = False,
        response_preference: Optional[str] = None,
        feedback_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new evaluation for a query run"""
        try:
            row: Dict[str, Any] = {
                "query_run_id": query_run_id,
                "evaluator_user_id": evaluator_user_id,
                "hallucination_flag": hallucination_flag
            }
            
            # Add scores if provided
            if overall_score is not None:
                row["overall_score"] = overall_score
            if accuracy_score is not None:
                row["accuracy_score"] = accuracy_score
            if relevance_score is not None:
                row["relevance_score"] = relevance_score
            if completeness_score is not None:
                row["completeness_score"] = completeness_score
            if clarity_score is not None:
                row["clarity_score"] = clarity_score
            if source_usefulness_score is not None:
                row["source_usefulness_score"] = source_usefulness_score
            if citation_quality_score is not None:
                row["citation_quality_score"] = citation_quality_score
            if response_preference is not None:
                row["response_preference"] = response_preference
            if feedback_text is not None:
                row["feedback_text"] = feedback_text
            
            rows = await self._supabase.insert("QueryRunEvaluations", rows=[row])
            
            if rows:
                return {"status": "success", "evaluation": rows[0]}
            else:
                return {"status": "error", "message": "Failed to create evaluation"}
                
        except SupabaseRestError as e:
            logger.error(f"Error creating evaluation: {e}")
            return {"status": "error", "message": str(e)}
    
    async def update_evaluation(
        self,
        evaluation_id: str,
        overall_score: Optional[int] = None,
        accuracy_score: Optional[int] = None,
        relevance_score: Optional[int] = None,
        completeness_score: Optional[int] = None,
        clarity_score: Optional[int] = None,
        source_usefulness_score: Optional[int] = None,
        citation_quality_score: Optional[int] = None,
        hallucination_flag: Optional[bool] = None,
        response_preference: Optional[str] = None,
        feedback_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update an existing evaluation"""
        try:
            patch: Dict[str, Any] = {}
            
            if overall_score is not None:
                patch["overall_score"] = overall_score
            if accuracy_score is not None:
                patch["accuracy_score"] = accuracy_score
            if relevance_score is not None:
                patch["relevance_score"] = relevance_score
            if completeness_score is not None:
                patch["completeness_score"] = completeness_score
            if clarity_score is not None:
                patch["clarity_score"] = clarity_score
            if source_usefulness_score is not None:
                patch["source_usefulness_score"] = source_usefulness_score
            if citation_quality_score is not None:
                patch["citation_quality_score"] = citation_quality_score
            if hallucination_flag is not None:
                patch["hallucination_flag"] = hallucination_flag
            if response_preference is not None:
                patch["response_preference"] = response_preference
            if feedback_text is not None:
                patch["feedback_text"] = feedback_text
            
            if not patch:
                return {"status": "error", "message": "Nothing to update"}
            
            rows = await self._supabase.update(
                "QueryRunEvaluations",
                patch=patch,
                filters={"id": f"eq.{evaluation_id}"}
            )
            
            if rows:
                return {"status": "success", "evaluation": rows[0]}
            else:
                return {"status": "error", "message": "Evaluation not found"}
                
        except SupabaseRestError as e:
            logger.error(f"Error updating evaluation: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_evaluation(self, evaluation_id: str) -> Dict[str, Any]:
        """Get an evaluation by ID"""
        try:
            rows = await self._supabase.select(
                "QueryRunEvaluations",
                select="*",
                filters={"id": f"eq.{evaluation_id}"}
            )
            
            if not rows:
                return {"status": "error", "message": "Evaluation not found"}
            
            return {"status": "success", "evaluation": rows[0]}
            
        except SupabaseRestError as e:
            logger.error(f"Error getting evaluation: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_query_run_evaluations(self, query_run_id: str) -> Dict[str, Any]:
        """Get all evaluations for a query run"""
        try:
            rows = await self._supabase.select(
                "QueryRunEvaluations",
                select="*",
                filters={"query_run_id": f"eq.{query_run_id}"},
                order="created_at.desc"
            )
            
            return {"status": "success", "evaluations": rows}
            
        except SupabaseRestError as e:
            logger.error(f"Error getting query run evaluations: {e}")
            return {"status": "error", "message": str(e)}
    
    async def list_evaluations(
        self,
        evaluator_user_id: Optional[str] = None,
        min_overall_score: Optional[int] = None,
        max_overall_score: Optional[int] = None,
        hallucination_flag: Optional[bool] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """List evaluations with filters"""
        try:
            filters: Dict[str, str] = {}
            
            if evaluator_user_id:
                filters["evaluator_user_id"] = f"eq.{evaluator_user_id}"
            if min_overall_score is not None:
                filters["overall_score"] = f"gte.{min_overall_score}"
            if max_overall_score is not None:
                filters["overall_score"] = f"lte.{max_overall_score}"
            if hallucination_flag is not None:
                filters["hallucination_flag"] = f"eq.{hallucination_flag}"
            
            rows = await self._supabase.select(
                "QueryRunEvaluations",
                select="*",
                filters=filters,
                order="created_at.desc",
                limit=limit
            )
            
            return {"status": "success", "evaluations": rows, "count": len(rows)}
            
        except SupabaseRestError as e:
            logger.error(f"Error listing evaluations: {e}")
            return {"status": "error", "message": str(e)}
    
    async def delete_evaluation(self, evaluation_id: str) -> Dict[str, Any]:
        """Delete an evaluation"""
        try:
            await self._supabase.delete(
                "QueryRunEvaluations",
                filters={"id": f"eq.{evaluation_id}"}
            )
            
            return {"status": "success", "message": "Evaluation deleted"}
            
        except SupabaseRestError as e:
            logger.error(f"Error deleting evaluation: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_evaluation_stats(
        self,
        collection: Optional[str] = None,
        use_case_type: Optional[str] = None,
        llm_model: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get aggregate evaluation statistics"""
        try:
            # Build query to join QueryRuns and QueryRunEvaluations
            # This is a simplified version - in production you'd use a more complex query
            
            filters: Dict[str, str] = {}
            if collection:
                filters["collection"] = f"eq.{collection}"
            if use_case_type:
                filters["use_case_type"] = f"eq.{use_case_type}"
            if llm_model:
                filters["llm_model"] = f"eq.{llm_model}"
            
            # Get all query runs matching filters
            query_runs = await self._supabase.select(
                "QueryRuns",
                select="id",
                filters=filters
            )
            
            if not query_runs:
                return {
                    "status": "success",
                    "stats": {
                        "total_evaluations": 0,
                        "avg_overall_score": None,
                        "avg_accuracy_score": None,
                        "avg_relevance_score": None,
                        "avg_completeness_score": None,
                        "avg_clarity_score": None,
                        "hallucination_count": 0
                    }
                }
            
            # Get evaluations for these query runs
            query_run_ids = [qr["id"] for qr in query_runs]
            all_evaluations = []
            
            for qr_id in query_run_ids:
                evals = await self._supabase.select(
                    "QueryRunEvaluations",
                    select="*",
                    filters={"query_run_id": f"eq.{qr_id}"}
                )
                all_evaluations.extend(evals)
            
            if not all_evaluations:
                return {
                    "status": "success",
                    "stats": {
                        "total_evaluations": 0,
                        "avg_overall_score": None,
                        "avg_accuracy_score": None,
                        "avg_relevance_score": None,
                        "avg_completeness_score": None,
                        "avg_clarity_score": None,
                        "hallucination_count": 0
                    }
                }
            
            # Calculate statistics
            total = len(all_evaluations)
            
            def avg_score(field: str) -> Optional[float]:
                scores = [e[field] for e in all_evaluations if e.get(field) is not None]
                return sum(scores) / len(scores) if scores else None
            
            hallucination_count = sum(1 for e in all_evaluations if e.get("hallucination_flag"))
            
            stats = {
                "total_evaluations": total,
                "avg_overall_score": avg_score("overall_score"),
                "avg_accuracy_score": avg_score("accuracy_score"),
                "avg_relevance_score": avg_score("relevance_score"),
                "avg_completeness_score": avg_score("completeness_score"),
                "avg_clarity_score": avg_score("clarity_score"),
                "avg_source_usefulness_score": avg_score("source_usefulness_score"),
                "avg_citation_quality_score": avg_score("citation_quality_score"),
                "hallucination_count": hallucination_count,
                "hallucination_rate": hallucination_count / total if total > 0 else 0
            }
            
            return {"status": "success", "stats": stats}
            
        except SupabaseRestError as e:
            logger.error(f"Error getting evaluation stats: {e}")
            return {"status": "error", "message": str(e)}
    
    async def quick_thumbs_evaluation(
        self,
        query_run_id: str,
        thumbs_up: bool,
        evaluator_user_id: str = "default_user"
    ) -> Dict[str, Any]:
        """Quick thumbs up/down evaluation"""
        overall_score = 5 if thumbs_up else 1
        response_preference = "preferred" if thumbs_up else "not_preferred"
        
        return await self.create_evaluation(
            query_run_id=query_run_id,
            evaluator_user_id=evaluator_user_id,
            overall_score=overall_score,
            response_preference=response_preference
        )
