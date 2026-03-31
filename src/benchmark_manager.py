import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime

from src.supabase_rest import SupabaseRestClient, SupabaseRestError
from src.retrieval_evaluation import BenchmarkQuery, RelevanceLabel


class BenchmarkManager:
    def __init__(self, supabase: Optional[SupabaseRestClient] = None):
        self._supabase = supabase
    
    async def create_benchmark_query(self, query: BenchmarkQuery) -> BenchmarkQuery:
        if not self._supabase:
            raise RuntimeError("Supabase is not configured")
        
        row = {
            "query_id": query.query_id,
            "collection": query.collection,
            "query_text": query.query_text,
            "query_type": query.query_type,
            "section_goal": query.section_goal,
            "difficulty": query.difficulty,
            "source": query.source,
            "source_metadata": query.source_metadata,
            "notes": query.notes,
            "is_active": query.is_active,
        }
        
        result = await self._supabase.insert("BenchmarkQueries", rows=[row])
        
        if result:
            return BenchmarkQuery(
                id=result[0].get("id"),
                query_id=result[0]["query_id"],
                collection=result[0]["collection"],
                query_text=result[0]["query_text"],
                query_type=result[0].get("query_type"),
                section_goal=result[0].get("section_goal"),
                difficulty=result[0].get("difficulty"),
                source=result[0].get("source"),
                source_metadata=result[0].get("source_metadata"),
                notes=result[0].get("notes"),
                is_active=result[0].get("is_active", True),
                created_at=datetime.fromisoformat(result[0]["created_at"].replace("Z", "+00:00")) if result[0].get("created_at") else None,
                updated_at=datetime.fromisoformat(result[0]["updated_at"].replace("Z", "+00:00")) if result[0].get("updated_at") else None,
            )
        
        return query
    
    async def bulk_create_benchmark_queries(self, queries: List[Dict[str, Any]]) -> List[BenchmarkQuery]:
        if not self._supabase:
            raise RuntimeError("Supabase is not configured")
        
        rows = []
        for q in queries:
            if "query_id" not in q:
                q["query_id"] = f"query_{uuid.uuid4().hex[:12]}"
            rows.append(q)
        
        result = await self._supabase.insert("BenchmarkQueries", rows=rows)
        
        created_queries = []
        for r in result:
            created_queries.append(BenchmarkQuery(
                id=r.get("id"),
                query_id=r["query_id"],
                collection=r["collection"],
                query_text=r["query_text"],
                query_type=r.get("query_type"),
                section_goal=r.get("section_goal"),
                difficulty=r.get("difficulty"),
                source=r.get("source"),
                source_metadata=r.get("source_metadata"),
                notes=r.get("notes"),
                is_active=r.get("is_active", True),
            ))
        
        return created_queries
    
    async def get_benchmark_query(self, query_id: str) -> Optional[BenchmarkQuery]:
        if not self._supabase:
            return None
        
        try:
            rows = await self._supabase.select(
                "BenchmarkQueries",
                filters={"query_id": f"eq.{query_id}"},
                limit=1,
            )
            
            if rows:
                r = rows[0]
                return BenchmarkQuery(
                    id=r.get("id"),
                    query_id=r["query_id"],
                    collection=r["collection"],
                    query_text=r["query_text"],
                    query_type=r.get("query_type"),
                    section_goal=r.get("section_goal"),
                    difficulty=r.get("difficulty"),
                    source=r.get("source"),
                    source_metadata=r.get("source_metadata"),
                    notes=r.get("notes"),
                    is_active=r.get("is_active", True),
                    created_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) if r.get("created_at") else None,
                    updated_at=datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00")) if r.get("updated_at") else None,
                )
        except SupabaseRestError:
            pass
        
        return None
    
    async def list_benchmark_queries(
        self,
        collection: Optional[str] = None,
        query_type: Optional[str] = None,
        is_active: bool = True,
    ) -> List[BenchmarkQuery]:
        if not self._supabase:
            return []
        
        filters = {}
        if collection:
            filters["collection"] = f"eq.{collection}"
        if query_type:
            filters["query_type"] = f"eq.{query_type}"
        if is_active:
            filters["is_active"] = "eq.true"
        
        try:
            rows = await self._supabase.select(
                "BenchmarkQueries",
                filters=filters,
                order="created_at.desc",
            )
            
            queries = []
            for r in rows:
                queries.append(BenchmarkQuery(
                    id=r.get("id"),
                    query_id=r["query_id"],
                    collection=r["collection"],
                    query_text=r["query_text"],
                    query_type=r.get("query_type"),
                    section_goal=r.get("section_goal"),
                    difficulty=r.get("difficulty"),
                    source=r.get("source"),
                    source_metadata=r.get("source_metadata"),
                    notes=r.get("notes"),
                    is_active=r.get("is_active", True),
                    created_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) if r.get("created_at") else None,
                    updated_at=datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00")) if r.get("updated_at") else None,
                ))
            
            return queries
        except SupabaseRestError:
            return []
    
    async def create_relevance_label(self, label: RelevanceLabel) -> RelevanceLabel:
        if not self._supabase:
            raise RuntimeError("Supabase is not configured")
        
        row = {
            "query_id": label.query_id,
            "collection": label.collection,
            "doc_id": label.doc_id,
            "doc_relevance": label.doc_relevance,
            "chunk_id": label.chunk_id,
            "chunk_index": label.chunk_index,
            "chunk_relevance": label.chunk_relevance,
            "evidence_role": label.evidence_role,
            "annotator": label.annotator,
            "confidence": label.confidence,
            "notes": label.notes,
        }
        
        result = await self._supabase.insert("BenchmarkRelevanceLabels", rows=[row])
        
        if result:
            r = result[0]
            return RelevanceLabel(
                id=r.get("id"),
                query_id=r["query_id"],
                collection=r["collection"],
                doc_id=r.get("doc_id"),
                doc_relevance=r.get("doc_relevance"),
                chunk_id=r.get("chunk_id"),
                chunk_index=r.get("chunk_index"),
                chunk_relevance=r.get("chunk_relevance"),
                evidence_role=r.get("evidence_role"),
                annotator=r.get("annotator"),
                confidence=r.get("confidence", 1.0),
                notes=r.get("notes"),
                created_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) if r.get("created_at") else None,
                updated_at=datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00")) if r.get("updated_at") else None,
            )
        
        return label
    
    async def bulk_create_relevance_labels(self, labels: List[Dict[str, Any]]) -> List[RelevanceLabel]:
        if not self._supabase:
            raise RuntimeError("Supabase is not configured")
        
        result = await self._supabase.insert("BenchmarkRelevanceLabels", rows=labels)
        
        created_labels = []
        for r in result:
            created_labels.append(RelevanceLabel(
                id=r.get("id"),
                query_id=r["query_id"],
                collection=r["collection"],
                doc_id=r.get("doc_id"),
                doc_relevance=r.get("doc_relevance"),
                chunk_id=r.get("chunk_id"),
                chunk_index=r.get("chunk_index"),
                chunk_relevance=r.get("chunk_relevance"),
                evidence_role=r.get("evidence_role"),
                annotator=r.get("annotator"),
                confidence=r.get("confidence", 1.0),
                notes=r.get("notes"),
            ))
        
        return created_labels
    
    async def get_labels_for_query(self, query_id: str) -> List[RelevanceLabel]:
        if not self._supabase:
            return []
        
        try:
            rows = await self._supabase.select(
                "BenchmarkRelevanceLabels",
                filters={"query_id": f"eq.{query_id}"},
            )
            
            labels = []
            for r in rows:
                labels.append(RelevanceLabel(
                    id=r.get("id"),
                    query_id=r["query_id"],
                    collection=r["collection"],
                    doc_id=r.get("doc_id"),
                    doc_relevance=r.get("doc_relevance"),
                    chunk_id=r.get("chunk_id"),
                    chunk_index=r.get("chunk_index"),
                    chunk_relevance=r.get("chunk_relevance"),
                    evidence_role=r.get("evidence_role"),
                    annotator=r.get("annotator"),
                    confidence=r.get("confidence", 1.0),
                    notes=r.get("notes"),
                    created_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) if r.get("created_at") else None,
                    updated_at=datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00")) if r.get("updated_at") else None,
                ))
            
            return labels
        except SupabaseRestError:
            return []
    
    async def get_labels_by_collection(self, collection: str) -> Dict[str, List[RelevanceLabel]]:
        if not self._supabase:
            return {}
        
        try:
            rows = await self._supabase.select(
                "BenchmarkRelevanceLabels",
                filters={"collection": f"eq.{collection}"},
            )
            
            labels_by_query: Dict[str, List[RelevanceLabel]] = {}
            for r in rows:
                query_id = r["query_id"]
                if query_id not in labels_by_query:
                    labels_by_query[query_id] = []
                
                labels_by_query[query_id].append(RelevanceLabel(
                    id=r.get("id"),
                    query_id=r["query_id"],
                    collection=r["collection"],
                    doc_id=r.get("doc_id"),
                    doc_relevance=r.get("doc_relevance"),
                    chunk_id=r.get("chunk_id"),
                    chunk_index=r.get("chunk_index"),
                    chunk_relevance=r.get("chunk_relevance"),
                    evidence_role=r.get("evidence_role"),
                    annotator=r.get("annotator"),
                    confidence=r.get("confidence", 1.0),
                    notes=r.get("notes"),
                ))
            
            return labels_by_query
        except SupabaseRestError:
            return {}
    
    async def update_relevance_label(self, label_id: int, updates: Dict[str, Any]) -> bool:
        if not self._supabase:
            raise RuntimeError("Supabase is not configured")
        
        allowed_fields = {
            "doc_relevance", "chunk_relevance", "evidence_role",
            "confidence", "notes", "annotator",
        }
        
        patch = {k: v for k, v in updates.items() if k in allowed_fields}
        
        if not patch:
            return False
        
        try:
            await self._supabase.update(
                "BenchmarkRelevanceLabels",
                patch=patch,
                filters={"id": f"eq.{label_id}"},
            )
            return True
        except SupabaseRestError:
            return False
    
    async def delete_relevance_label(self, label_id: int) -> bool:
        if not self._supabase:
            raise RuntimeError("Supabase is not configured")
        
        try:
            await self._supabase.delete(
                "BenchmarkRelevanceLabels",
                filters={"id": f"eq.{label_id}"},
            )
            return True
        except SupabaseRestError:
            return False
    
    async def create_annotation_session(
        self,
        collection: str,
        annotator: str,
    ) -> str:
        if not self._supabase:
            raise RuntimeError("Supabase is not configured")
        
        session_id = f"session_{uuid.uuid4().hex[:12]}"
        
        row = {
            "session_id": session_id,
            "collection": collection,
            "annotator": annotator,
            "queries_annotated": 0,
            "labels_created": 0,
        }
        
        await self._supabase.insert("AnnotationSessions", rows=[row])
        
        return session_id
    
    async def update_annotation_session(
        self,
        session_id: str,
        queries_annotated: Optional[int] = None,
        labels_created: Optional[int] = None,
        completed: bool = False,
    ) -> bool:
        if not self._supabase:
            raise RuntimeError("Supabase is not configured")
        
        patch: Dict[str, Any] = {"last_activity_at": datetime.utcnow().isoformat()}
        
        if queries_annotated is not None:
            patch["queries_annotated"] = queries_annotated
        if labels_created is not None:
            patch["labels_created"] = labels_created
        if completed:
            patch["completed_at"] = datetime.utcnow().isoformat()
        
        try:
            await self._supabase.update(
                "AnnotationSessions",
                patch=patch,
                filters={"session_id": f"eq.{session_id}"},
            )
            return True
        except SupabaseRestError:
            return False
