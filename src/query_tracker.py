import logging
import time
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime

from src.supabase_rest import SupabaseRestClient, SupabaseRestError

logger = logging.getLogger(__name__)


class QueryTracker:
    """Tracks query runs, retrieval results, and document usage"""
    
    def __init__(self, supabase: SupabaseRestClient):
        self._supabase = supabase
    
    async def create_query_run(
        self,
        user_query: str,
        collection: str,
        user_id: str = "default_user",
        session_id: Optional[str] = None,
        message_id: Optional[str] = None,
        project_id: Optional[str] = None,
        retrieval_mode: Optional[str] = None,
        retrieval_profile: Optional[str] = None,
        top_k: Optional[int] = None,
        llm_model: Optional[str] = None,
        embedding_model: Optional[str] = None,
        use_case_type: Optional[str] = None,
        metadata_filters: Optional[Dict[str, Any]] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a new query run record"""
        try:
            row: Dict[str, Any] = {
                "user_query": user_query,
                "collection": collection,
                "user_id": user_id
            }
            
            # Add optional fields
            if session_id:
                row["session_id"] = session_id
            if message_id:
                row["message_id"] = message_id
            if project_id:
                row["project_id"] = project_id
            if retrieval_mode:
                row["retrieval_mode"] = retrieval_mode
            if retrieval_profile:
                row["retrieval_profile"] = retrieval_profile
            if top_k:
                row["top_k"] = top_k
            if llm_model:
                row["llm_model"] = llm_model
            if embedding_model:
                row["embedding_model"] = embedding_model
            if use_case_type:
                row["use_case_type"] = use_case_type
            if metadata_filters:
                row["metadata_filters_used"] = metadata_filters
            if config:
                row["run_config_json"] = config
            
            rows = await self._supabase.insert("QueryRuns", rows=[row])
            
            if rows:
                return {"status": "success", "query_run": rows[0]}
            else:
                return {"status": "error", "message": "Failed to create query run"}
                
        except SupabaseRestError as e:
            logger.error(f"Error creating query run: {e}")
            return {"status": "error", "message": str(e)}
    
    async def update_query_run(
        self,
        query_run_id: str,
        final_response: Optional[str] = None,
        response_time_ms: Optional[float] = None,
        retrieval_time_ms: Optional[float] = None,
        llm_time_ms: Optional[float] = None,
        token_input: Optional[int] = None,
        token_output: Optional[int] = None,
        estimated_cost: Optional[float] = None,
        top_k_sent_to_llm: Optional[int] = None,
        reranker_used: Optional[bool] = None,
        reranker_model: Optional[str] = None,
        temperature: Optional[float] = None,
        prompt_template_version: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update query run with response and metrics"""
        try:
            patch: Dict[str, Any] = {}
            
            if final_response is not None:
                patch["final_response"] = final_response
            if response_time_ms is not None:
                patch["response_time_ms"] = response_time_ms
            if retrieval_time_ms is not None:
                patch["retrieval_time_ms"] = retrieval_time_ms
            if llm_time_ms is not None:
                patch["llm_time_ms"] = llm_time_ms
            if token_input is not None:
                patch["token_input"] = token_input
            if token_output is not None:
                patch["token_output"] = token_output
            if estimated_cost is not None:
                patch["estimated_cost"] = estimated_cost
            if top_k_sent_to_llm is not None:
                patch["top_k_sent_to_llm"] = top_k_sent_to_llm
            if reranker_used is not None:
                patch["reranker_used"] = reranker_used
            if reranker_model is not None:
                patch["reranker_model"] = reranker_model
            if temperature is not None:
                patch["temperature"] = temperature
            if prompt_template_version is not None:
                patch["prompt_template_version"] = prompt_template_version
            
            if not patch:
                return {"status": "error", "message": "Nothing to update"}
            
            rows = await self._supabase.update(
                "QueryRuns",
                patch=patch,
                filters={"id": f"eq.{query_run_id}"}
            )
            
            if rows:
                return {"status": "success", "query_run": rows[0]}
            else:
                return {"status": "error", "message": "Query run not found"}
                
        except SupabaseRestError as e:
            logger.error(f"Error updating query run: {e}")
            return {"status": "error", "message": str(e)}
    
    async def track_retrieved_documents(
        self,
        query_run_id: str,
        retrieved_results: List[Dict[str, Any]],
        collection: str
    ) -> Dict[str, Any]:
        """Track which documents/chunks were retrieved"""
        try:
            rows_to_insert = []
            
            for rank, result in enumerate(retrieved_results, start=1):
                doc_id = result.get("doc_id")
                chunk_index = result.get("chunk_index")
                
                if not doc_id:
                    continue
                
                # Get document ID from database
                doc_result = await self._get_document_id(collection, doc_id)
                if doc_result["status"] != "success":
                    continue
                
                document_id = doc_result["document_id"]
                chunk_id = await self._get_chunk_id(collection, doc_id, chunk_index) if chunk_index is not None else None
                
                row = {
                    "query_run_id": query_run_id,
                    "document_id": document_id,
                    "retrieval_rank": rank,
                    "retrieval_score": result.get("score") or result.get("rank", 0.0),
                    "retrieval_source": result.get("source", "unknown"),
                    "was_retrieved": True,
                    "contribution_type": "retrieved"
                }
                
                if chunk_id:
                    row["chunk_id"] = chunk_id
                
                rows_to_insert.append(row)
            
            if rows_to_insert:
                await self._supabase.insert("QueryRunDocuments", rows=rows_to_insert)
                return {"status": "success", "tracked": len(rows_to_insert)}
            else:
                return {"status": "success", "tracked": 0}
                
        except SupabaseRestError as e:
            logger.error(f"Error tracking retrieved documents: {e}")
            return {"status": "error", "message": str(e)}
    
    async def mark_documents_in_context(
        self,
        query_run_id: str,
        context_doc_ids: List[str],
        collection: str
    ) -> Dict[str, Any]:
        """Mark which documents made it into the LLM context"""
        try:
            for doc_id in context_doc_ids:
                # Get document ID
                doc_result = await self._get_document_id(collection, doc_id)
                if doc_result["status"] != "success":
                    continue
                
                document_id = doc_result["document_id"]
                
                # Update existing QueryRunDocuments record
                await self._supabase.update(
                    "QueryRunDocuments",
                    patch={
                        "was_in_context": True,
                        "contribution_type": "supporting"
                    },
                    filters={
                        "query_run_id": f"eq.{query_run_id}",
                        "document_id": f"eq.{document_id}"
                    }
                )
            
            return {"status": "success", "marked": len(context_doc_ids)}
            
        except SupabaseRestError as e:
            logger.error(f"Error marking context documents: {e}")
            return {"status": "error", "message": str(e)}
    
    async def mark_cited_documents(
        self,
        query_run_id: str,
        cited_doc_ids: List[str],
        collection: str
    ) -> Dict[str, Any]:
        """Mark which documents were cited in the response"""
        try:
            for doc_id in cited_doc_ids:
                # Get document ID
                doc_result = await self._get_document_id(collection, doc_id)
                if doc_result["status"] != "success":
                    continue
                
                document_id = doc_result["document_id"]
                
                # Update existing QueryRunDocuments record
                await self._supabase.update(
                    "QueryRunDocuments",
                    patch={
                        "was_cited": True,
                        "contribution_type": "cited"
                    },
                    filters={
                        "query_run_id": f"eq.{query_run_id}",
                        "document_id": f"eq.{document_id}"
                    }
                )
            
            return {"status": "success", "marked": len(cited_doc_ids)}
            
        except SupabaseRestError as e:
            logger.error(f"Error marking cited documents: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_query_run(self, query_run_id: str) -> Dict[str, Any]:
        """Get a query run by ID"""
        try:
            rows = await self._supabase.select(
                "QueryRuns",
                select="*",
                filters={"id": f"eq.{query_run_id}"}
            )
            
            if not rows:
                return {"status": "error", "message": "Query run not found"}
            
            return {"status": "success", "query_run": rows[0]}
            
        except SupabaseRestError as e:
            logger.error(f"Error getting query run: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_query_run_documents(self, query_run_id: str) -> Dict[str, Any]:
        """Get all documents associated with a query run"""
        try:
            rows = await self._supabase.select(
                "QueryRunDocuments",
                select="*",
                filters={"query_run_id": f"eq.{query_run_id}"},
                order="retrieval_rank.asc"
            )
            
            return {"status": "success", "documents": rows}
            
        except SupabaseRestError as e:
            logger.error(f"Error getting query run documents: {e}")
            return {"status": "error", "message": str(e)}
    
    async def list_query_runs(
        self,
        collection: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: str = "default_user",
        use_case_type: Optional[str] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """List query runs with filters"""
        try:
            filters = {"user_id": f"eq.{user_id}"}
            
            if collection:
                filters["collection"] = f"eq.{collection}"
            if session_id:
                filters["session_id"] = f"eq.{session_id}"
            if use_case_type:
                filters["use_case_type"] = f"eq.{use_case_type}"
            
            rows = await self._supabase.select(
                "QueryRuns",
                select="*",
                filters=filters,
                order="created_at.desc",
                limit=limit
            )
            
            return {"status": "success", "query_runs": rows, "count": len(rows)}
            
        except SupabaseRestError as e:
            logger.error(f"Error listing query runs: {e}")
            return {"status": "error", "message": str(e)}
    
    async def _get_document_id(self, collection: str, doc_id: str) -> Dict[str, Any]:
        """Get database document ID from collection and doc_id"""
        try:
            rows = await self._supabase.select(
                "Documents",
                select="id",
                filters={
                    "collection": f"eq.{collection}",
                    "doc_id": f"eq.{doc_id}"
                }
            )
            
            if rows:
                return {"status": "success", "document_id": rows[0]["id"]}
            else:
                return {"status": "error", "message": "Document not found"}
                
        except SupabaseRestError as e:
            logger.error(f"Error getting document ID: {e}")
            return {"status": "error", "message": str(e)}
    
    async def _get_chunk_id(self, collection: str, doc_id: str, chunk_index: int) -> Optional[int]:
        """Get database chunk ID from collection, doc_id, and chunk_index"""
        try:
            rows = await self._supabase.select(
                "DocumentChunks",
                select="id",
                filters={
                    "collection": f"eq.{collection}",
                    "doc_id": f"eq.{doc_id}",
                    "chunk_index": f"eq.{chunk_index}"
                }
            )
            
            if rows:
                return rows[0]["id"]
            else:
                return None
                
        except SupabaseRestError as e:
            logger.error(f"Error getting chunk ID: {e}")
            return None
    
    def extract_cited_doc_ids(self, response_text: str, sources: Optional[List[Dict[str, Any]]]) -> List[str]:
        """Extract doc_ids that were cited in the response"""
        cited_ids = []
        
        # If sources are provided, use them
        if sources:
            for source in sources:
                doc_id = source.get("doc_id")
                if doc_id and doc_id not in cited_ids:
                    cited_ids.append(doc_id)
        
        # Could also parse citations from response text if needed
        # For now, rely on sources parameter
        
        return cited_ids
    
    def extract_context_doc_ids(self, context_chunks: List[Dict[str, Any]]) -> List[str]:
        """Extract unique doc_ids from context chunks"""
        doc_ids = []
        
        for chunk in context_chunks:
            doc_id = chunk.get("doc_id")
            if doc_id and doc_id not in doc_ids:
                doc_ids.append(doc_id)
        
        return doc_ids
