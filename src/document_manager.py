import logging
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime
from pathlib import Path

from src.supabase_rest import SupabaseRestClient, SupabaseRestError

logger = logging.getLogger(__name__)


class DocumentManager:
    """Manages document lifecycle, metadata, and ingestion tracking"""
    
    def __init__(self, supabase: SupabaseRestClient):
        self._supabase = supabase
    
    async def create_document(
        self,
        collection: str,
        doc_id: Optional[str] = None,
        title: Optional[str] = None,
        filename: Optional[str] = None,
        file_path: Optional[str] = None,
        document_type: Optional[str] = None,
        author: Optional[str] = None,
        year: Optional[int] = None,
        doi: Optional[str] = None,
        abstract: Optional[str] = None,
        notes: Optional[str] = None,
        tags: Optional[List[str]] = None,
        apa7_reference: Optional[str] = None,
        source_type: str = "manual_entry",
        user_id: str = "default_user",
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new document record (with or without PDF)"""
        try:
            # Generate doc_id if not provided
            if not doc_id:
                doc_id = str(uuid.uuid4())
            
            # Build document record
            row: Dict[str, Any] = {
                "collection": collection,
                "doc_id": doc_id,
                "user_id": user_id,
                "source_type": source_type,
                "pdf_attached": bool(file_path),
                "ingestion_status": "not_uploaded" if not file_path else "queued",
                "is_active": True,
            }
            
            # Add optional fields
            if title:
                row["title"] = title
            if filename:
                row["filename"] = filename
            if file_path:
                row["file_path"] = file_path
            if document_type:
                row["document_type"] = document_type
            if author:
                row["author"] = author
            if year:
                row["year"] = year
            if doi:
                row["doi"] = doi
            if abstract:
                row["abstract"] = abstract
            if notes:
                row["notes"] = notes
            if tags:
                row["tags"] = tags
            if apa7_reference:
                row["apa7_reference"] = apa7_reference
            if project_id:
                row["project_id"] = project_id
            
            # Calculate metadata completeness
            row["metadata_complete"] = self._is_metadata_complete(row)
            
            # Insert document
            rows = await self._supabase.insert("Documents", rows=[row])
            
            if rows:
                return {"status": "success", "document": rows[0]}
            else:
                return {"status": "error", "message": "Failed to create document"}
                
        except SupabaseRestError as e:
            logger.error(f"Error creating document: {e}")
            return {"status": "error", "message": str(e)}
    
    async def list_documents(
        self,
        collection: Optional[str] = None,
        project_id: Optional[str] = None,
        user_id: str = "default_user",
        ingestion_status: Optional[str] = None,
        document_type: Optional[str] = None,
        pdf_attached: Optional[bool] = None,
        is_active: bool = True,
        limit: int = 100
    ) -> Dict[str, Any]:
        """List documents with filters"""
        try:
            filters: Dict[str, str] = {"user_id": f"eq.{user_id}"}
            
            if is_active is not None:
                filters["is_active"] = f"eq.{is_active}"
            if collection:
                filters["collection"] = f"eq.{collection}"
            if project_id:
                filters["project_id"] = f"eq.{project_id}"
            if ingestion_status:
                filters["ingestion_status"] = f"eq.{ingestion_status}"
            if document_type:
                filters["document_type"] = f"eq.{document_type}"
            if pdf_attached is not None:
                filters["pdf_attached"] = f"eq.{pdf_attached}"
            
            rows = await self._supabase.select(
                "Documents",
                select="*",
                filters=filters,
                order="updated_at.desc",
                limit=limit
            )
            
            # If Documents table is empty, try DocumentPerformanceSummary first, then DocumentChunks
            if not rows or len(rows) == 0:
                logger.info("Documents table empty, trying DocumentPerformanceSummary")
                
                # Try DocumentPerformanceSummary (has stats but requires Documents table)
                perf_filters: Dict[str, str] = {"user_id": f"eq.{user_id}"}
                if is_active is not None:
                    perf_filters["is_active"] = f"eq.{is_active}"
                if collection:
                    perf_filters["collection"] = f"eq.{collection}"
                
                try:
                    rows = await self._supabase.select(
                        "DocumentPerformanceSummary",
                        select="*",
                        filters=perf_filters,
                        limit=limit
                    )
                    if rows and len(rows) > 0:
                        logger.info(f"Found {len(rows)} documents from DocumentPerformanceSummary")
                        return {"status": "success", "documents": rows, "count": len(rows)}
                except Exception as e:
                    logger.info(f"DocumentPerformanceSummary query failed: {e}")
                
                # Fall back to DocumentChunks for legacy data
                logger.info("Falling back to DocumentChunks")
                chunk_filters: Dict[str, str] = {}
                if collection:
                    chunk_filters["collection"] = f"eq.{collection}"
                
                chunks = await self._supabase.select(
                    "DocumentChunks",
                    select="collection,doc_id,filename,metadata",
                    filters=chunk_filters,
                    limit=1000  # Get more to deduplicate
                )
                
                # Deduplicate by doc_id and create document-like objects
                seen_docs = {}
                for chunk in chunks:
                    doc_id = chunk.get("doc_id")
                    if doc_id and doc_id not in seen_docs:
                        metadata = chunk.get("metadata", {})
                        seen_docs[doc_id] = {
                            "id": None,  # No ID in old system
                            "collection": chunk.get("collection"),
                            "doc_id": doc_id,
                            "filename": chunk.get("filename"),
                            "title": metadata.get("title") or chunk.get("filename"),
                            "author": metadata.get("author"),
                            "year": metadata.get("year"),
                            "document_type": None,
                            "pdf_attached": True,  # Assume true for legacy docs
                            "ingestion_status": "complete",  # Assume complete for legacy docs
                            "is_active": True,
                            "user_id": user_id,
                            "created_at": None,
                            "updated_at": None
                        }
                
                rows = list(seen_docs.values())[:limit]
                logger.info(f"Found {len(rows)} unique documents from DocumentChunks")
            
            return {"status": "success", "documents": rows, "count": len(rows)}
            
        except SupabaseRestError as e:
            logger.error(f"Error listing documents: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_document(self, document_id: int) -> Dict[str, Any]:
        """Get a single document by ID"""
        try:
            rows = await self._supabase.select(
                "Documents",
                select="*",
                filters={"id": f"eq.{document_id}"}
            )
            
            if not rows:
                return {"status": "error", "message": "Document not found"}
            
            return {"status": "success", "document": rows[0]}
            
        except SupabaseRestError as e:
            logger.error(f"Error getting document: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_document_by_doc_id(self, collection: str, doc_id: str) -> Dict[str, Any]:
        """Get a document by collection and doc_id"""
        try:
            rows = await self._supabase.select(
                "Documents",
                select="*",
                filters={
                    "collection": f"eq.{collection}",
                    "doc_id": f"eq.{doc_id}"
                }
            )
            
            if not rows:
                return {"status": "error", "message": "Document not found"}
            
            return {"status": "success", "document": rows[0]}
            
        except SupabaseRestError as e:
            logger.error(f"Error getting document: {e}")
            return {"status": "error", "message": str(e)}
    
    async def update_document(
        self,
        document_id: int,
        title: Optional[str] = None,
        document_type: Optional[str] = None,
        author: Optional[str] = None,
        year: Optional[int] = None,
        doi: Optional[str] = None,
        abstract: Optional[str] = None,
        notes: Optional[str] = None,
        tags: Optional[List[str]] = None,
        needs_review: Optional[bool] = None,
        is_active: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Update document metadata"""
        try:
            patch: Dict[str, Any] = {}
            
            if title is not None:
                patch["title"] = title
            if document_type is not None:
                patch["document_type"] = document_type
            if author is not None:
                patch["author"] = author
            if year is not None:
                patch["year"] = year
            if doi is not None:
                patch["doi"] = doi
            if abstract is not None:
                patch["abstract"] = abstract
            if notes is not None:
                patch["notes"] = notes
            if tags is not None:
                patch["tags"] = tags
            if needs_review is not None:
                patch["needs_review"] = needs_review
            if is_active is not None:
                patch["is_active"] = is_active
            
            if not patch:
                return {"status": "error", "message": "Nothing to update"}
            
            # Recalculate metadata completeness
            doc_result = await self.get_document(document_id)
            if doc_result["status"] == "success":
                doc = doc_result["document"]
                updated_doc = {**doc, **patch}
                patch["metadata_complete"] = self._is_metadata_complete(updated_doc)
            
            rows = await self._supabase.update(
                "Documents",
                patch=patch,
                filters={"id": f"eq.{document_id}"}
            )
            
            if rows:
                return {"status": "success", "document": rows[0]}
            else:
                return {"status": "error", "message": "Document not found"}
                
        except SupabaseRestError as e:
            logger.error(f"Error updating document: {e}")
            return {"status": "error", "message": str(e)}
    
    async def attach_pdf(
        self,
        document_id: int,
        file_path: str,
        filename: str,
        file_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """Attach a PDF to an existing document record"""
        try:
            patch = {
                "file_path": file_path,
                "filename": filename,
                "pdf_attached": True,
                "ingestion_status": "queued"
            }
            
            if file_size:
                patch["file_size"] = file_size
            
            rows = await self._supabase.update(
                "Documents",
                patch=patch,
                filters={"id": f"eq.{document_id}"}
            )
            
            if rows:
                return {"status": "success", "document": rows[0]}
            else:
                return {"status": "error", "message": "Document not found"}
                
        except SupabaseRestError as e:
            logger.error(f"Error attaching PDF: {e}")
            return {"status": "error", "message": str(e)}
    
    async def delete_document(self, document_id: int) -> Dict[str, Any]:
        """Delete a document (soft delete by default)"""
        try:
            # Soft delete - mark as inactive
            rows = await self._supabase.update(
                "Documents",
                patch={"is_active": False},
                filters={"id": f"eq.{document_id}"}
            )
            
            if rows:
                return {"status": "success", "message": "Document deleted"}
            else:
                return {"status": "error", "message": "Document not found"}
                
        except SupabaseRestError as e:
            logger.error(f"Error deleting document: {e}")
            return {"status": "error", "message": str(e)}
    
    async def hard_delete_document(self, document_id: int) -> Dict[str, Any]:
        """Permanently delete a document and all related data"""
        try:
            await self._supabase.delete(
                "Documents",
                filters={"id": f"eq.{document_id}"}
            )
            
            return {"status": "success", "message": "Document permanently deleted"}
            
        except SupabaseRestError as e:
            logger.error(f"Error hard deleting document: {e}")
            return {"status": "error", "message": str(e)}
    
    async def create_ingestion_job(
        self,
        document_id: int,
        collection: str,
        doc_id: str,
        parser_used: Optional[str] = None,
        chunking_method: Optional[str] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        embedding_model: Optional[str] = None,
        triggered_by: str = "user"
    ) -> Dict[str, Any]:
        """Create an ingestion job record"""
        try:
            row = {
                "document_id": document_id,
                "collection": collection,
                "doc_id": doc_id,
                "status": "queued",
                "triggered_by": triggered_by
            }
            
            if parser_used:
                row["parser_used"] = parser_used
            if chunking_method:
                row["chunking_method"] = chunking_method
            if chunk_size:
                row["chunk_size"] = chunk_size
            if chunk_overlap:
                row["chunk_overlap"] = chunk_overlap
            if embedding_model:
                row["embedding_model"] = embedding_model
            
            rows = await self._supabase.insert("DocumentIngestionJobs", rows=[row])
            
            if rows:
                return {"status": "success", "job": rows[0]}
            else:
                return {"status": "error", "message": "Failed to create job"}
                
        except SupabaseRestError as e:
            logger.error(f"Error creating ingestion job: {e}")
            return {"status": "error", "message": str(e)}
    
    async def update_ingestion_job(
        self,
        job_id: str,
        status: Optional[str] = None,
        chunks_created: Optional[int] = None,
        error_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update an ingestion job status"""
        try:
            patch: Dict[str, Any] = {}
            
            if status:
                patch["status"] = status
                if status in ["complete", "failed"]:
                    patch["completed_at"] = datetime.now().isoformat()
            
            if chunks_created is not None:
                patch["chunks_created"] = chunks_created
            
            if error_message is not None:
                patch["error_message"] = error_message
            
            if not patch:
                return {"status": "error", "message": "Nothing to update"}
            
            rows = await self._supabase.update(
                "DocumentIngestionJobs",
                patch=patch,
                filters={"id": f"eq.{job_id}"}
            )
            
            if rows:
                return {"status": "success", "job": rows[0]}
            else:
                return {"status": "error", "message": "Job not found"}
                
        except SupabaseRestError as e:
            logger.error(f"Error updating ingestion job: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_document_jobs(self, document_id: int) -> Dict[str, Any]:
        """Get all ingestion jobs for a document"""
        try:
            rows = await self._supabase.select(
                "DocumentIngestionJobs",
                select="*",
                filters={"document_id": f"eq.{document_id}"},
                order="created_at.desc"
            )
            
            return {"status": "success", "jobs": rows}
            
        except SupabaseRestError as e:
            logger.error(f"Error getting document jobs: {e}")
            return {"status": "error", "message": str(e)}
    
    async def list_jobs_by_status(
        self,
        status: Optional[str] = None,
        collection: Optional[str] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """List ingestion jobs by status"""
        try:
            filters: Dict[str, str] = {}
            if status:
                filters["status"] = f"eq.{status}"
            if collection:
                filters["collection"] = f"eq.{collection}"
            
            rows = await self._supabase.select(
                "DocumentIngestionJobs",
                select="*",
                filters=filters,
                order="created_at.desc",
                limit=limit
            )
            
            return {"status": "success", "jobs": rows}
            
        except SupabaseRestError as e:
            logger.error(f"Error listing jobs: {e}")
            return {"status": "error", "message": str(e)}
    
    async def update_document_ingestion_status(
        self,
        document_id: int,
        status: str,
        chunk_count: Optional[int] = None,
        embedding_model: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update document ingestion status"""
        try:
            patch: Dict[str, Any] = {"ingestion_status": status}
            
            if status == "complete":
                patch["ingested_at"] = datetime.now().isoformat()
            
            if chunk_count is not None:
                patch["chunk_count"] = chunk_count
            
            if embedding_model:
                patch["embedding_model"] = embedding_model
            
            if error_message:
                patch["processing_error"] = error_message
                patch["needs_review"] = True
            
            rows = await self._supabase.update(
                "Documents",
                patch=patch,
                filters={"id": f"eq.{document_id}"}
            )
            
            if rows:
                return {"status": "success", "document": rows[0]}
            else:
                return {"status": "error", "message": "Document not found"}
                
        except SupabaseRestError as e:
            logger.error(f"Error updating document status: {e}")
            return {"status": "error", "message": str(e)}
    
    def _is_metadata_complete(self, doc: Dict[str, Any]) -> bool:
        """Check if document has complete metadata"""
        required_fields = ["title", "filename", "collection", "doc_id", "source_type"]
        
        for field in required_fields:
            if not doc.get(field):
                return False
        
        # Check for recommended fields
        recommended_score = 0
        if doc.get("author"):
            recommended_score += 1
        if doc.get("year"):
            recommended_score += 1
        if doc.get("document_type"):
            recommended_score += 1
        if doc.get("abstract"):
            recommended_score += 1
        
        # Consider complete if has all required + at least 2 recommended
        return recommended_score >= 2
    
    async def get_document_performance(
        self,
        collection: Optional[str] = None,
        user_id: str = "default_user",
        limit: int = 100
    ) -> Dict[str, Any]:
        """Get document performance summary from materialized view"""
        try:
            filters = {"user_id": f"eq.{user_id}"}
            if collection:
                filters["collection"] = f"eq.{collection}"
            
            rows = await self._supabase.select(
                "DocumentPerformanceSummary",
                select="*",
                filters=filters,
                order="total_retrievals.desc",
                limit=limit
            )
            
            return {"status": "success", "documents": rows}
            
        except SupabaseRestError as e:
            logger.error(f"Error getting document performance: {e}")
            return {"status": "error", "message": str(e)}
    
    async def refresh_performance_summary(self) -> Dict[str, Any]:
        """Refresh the materialized view"""
        try:
            await self._supabase.rpc("refresh_document_performance_summary", payload={})
            return {"status": "success", "message": "Performance summary refreshed"}
        except SupabaseRestError as e:
            logger.error(f"Error refreshing performance summary: {e}")
            return {"status": "error", "message": str(e)}
    
    async def bulk_import_documents(
        self,
        documents: List[Dict[str, Any]],
        collection: str,
        user_id: str = "default_user",
        source_type: str = "csv_import"
    ) -> Dict[str, Any]:
        """Bulk import documents from CSV or other source"""
        try:
            imported = []
            errors = []
            
            for idx, doc_data in enumerate(documents):
                try:
                    # Generate doc_id if not provided
                    doc_id = doc_data.get("id") or doc_data.get("doc_id") or str(uuid.uuid4())
                    
                    # Build document record
                    row: Dict[str, Any] = {
                        "collection": collection,
                        "doc_id": doc_id,
                        "user_id": user_id,
                        "source_type": source_type,
                        "pdf_attached": False,
                        "ingestion_status": "not_uploaded",
                        "is_active": True,
                    }
                    
                    # Map CSV fields to database fields
                    field_mapping = {
                        "title": "title",
                        "filename": "filename",
                        "document_type": "document_type",
                        "author": "author",
                        "year": "year",
                        "doi": "doi",
                        "abstract": "abstract",
                        "notes": "notes",
                        "tags": "tags",
                        "file_path": "file_path",
                        "apa7_reference": "apa7_reference",
                    }
                    
                    for csv_field, db_field in field_mapping.items():
                        if csv_field in doc_data and doc_data[csv_field]:
                            value = doc_data[csv_field]
                            
                            # Handle year conversion
                            if db_field == "year" and isinstance(value, str):
                                try:
                                    value = int(value)
                                except ValueError:
                                    logger.warning(f"Invalid year value: {value}")
                                    continue
                            
                            # Handle tags - convert string to list if needed
                            if db_field == "tags" and isinstance(value, str):
                                value = [tag.strip() for tag in value.split(",") if tag.strip()]
                            
                            row[db_field] = value
                    
                    # If file_path is provided, mark as having PDF
                    if row.get("file_path"):
                        row["pdf_attached"] = True
                        row["ingestion_status"] = "queued"
                    
                    # Calculate metadata completeness
                    row["metadata_complete"] = self._is_metadata_complete(row)
                    
                    # Insert document
                    rows = await self._supabase.insert("Documents", rows=[row])
                    
                    if rows:
                        imported.append(rows[0])
                    else:
                        errors.append({
                            "row": idx + 1,
                            "error": "Failed to insert document"
                        })
                        
                except Exception as e:
                    logger.error(f"Error importing document at row {idx + 1}: {e}")
                    errors.append({
                        "row": idx + 1,
                        "error": str(e)
                    })
            
            return {
                "status": "success" if imported else "error",
                "imported_count": len(imported),
                "error_count": len(errors),
                "imported": imported,
                "errors": errors
            }
            
        except Exception as e:
            logger.error(f"Error in bulk import: {e}")
            return {"status": "error", "message": str(e)}
