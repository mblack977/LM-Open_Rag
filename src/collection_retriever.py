import asyncio
import logging
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass

from .hybrid_retrieval import HybridRetrievalEngine, RetrievalCandidate
from .query_planner import QueryPlan
from .supabase_rest import SupabaseRestClient
from .vector_store import VectorStore
from .embeddings import EmbeddingGenerator

logger = logging.getLogger(__name__)


@dataclass
class DocumentMetadata:
    """Metadata for a document in the collection."""
    doc_id: str
    title: Optional[str]
    authors: Optional[str]
    abstract: Optional[str]
    filename: Optional[str]
    tags: List[str]
    relevance_score: float = 0.0


@dataclass
class ChunkResult:
    """A retrieved chunk with metadata."""
    doc_id: str
    chunk_index: int
    text: str
    score: float
    filename: Optional[str]
    title: Optional[str]
    authors: Optional[str]
    section: Optional[str]


@dataclass
class EvidencePack:
    """Complete evidence package for answering a query."""
    query_text: str
    plan: QueryPlan
    candidate_documents: List[DocumentMetadata]
    chunks: List[ChunkResult]
    total_documents_searched: int


class CollectionRetriever:
    """
    Multi-stage retrieval system for collection-aware research queries.
    
    Stage 1: Search document metadata and abstracts
    Stage 2: Identify candidate documents
    Stage 3: Retrieve targeted chunks from candidates
    """
    
    def __init__(
        self,
        supabase: SupabaseRestClient,
        vector_store: VectorStore,
        embedding_generator: EmbeddingGenerator
    ):
        self._supabase = supabase
        self._vector_store = vector_store
        self._embedding_generator = embedding_generator
        self._hybrid_engine = HybridRetrievalEngine()
    
    async def retrieve(
        self,
        query_text: str,
        plan: QueryPlan,
        collection: str
    ) -> EvidencePack:
        """
        Execute a multi-stage retrieval based on the query plan.
        """
        logger.info(f"Executing retrieval plan: intent={plan.intent}, scope={plan.scope}")
        
        # Stage 1: Search document metadata
        candidate_docs = await self._search_document_metadata(
            collection=collection,
            search_terms=plan.search_terms,
            minimum_documents=plan.minimum_documents
        )
        
        logger.info(f"Found {len(candidate_docs)} candidate documents")
        
        # Stage 2: Retrieve chunks if needed
        chunks: List[ChunkResult] = []
        if plan.use_chunks and candidate_docs:
            chunks = await self._retrieve_targeted_chunks(
                collection=collection,
                query_text=query_text,
                candidate_doc_ids=[doc.doc_id for doc in candidate_docs],
                plan=plan
            )
            logger.info(f"Retrieved {len(chunks)} chunks")
        
        # Get total document count
        total_docs = await self._get_total_document_count(collection)
        
        return EvidencePack(
            query_text=query_text,
            plan=plan,
            candidate_documents=candidate_docs,
            chunks=chunks,
            total_documents_searched=total_docs
        )
    
    async def _search_document_metadata(
        self,
        collection: str,
        search_terms: List[str],
        minimum_documents: int
    ) -> List[DocumentMetadata]:
        """
        Stage 1: Search document metadata and abstracts to identify candidates.
        """
        try:
            # Query the Documents table
            filters = {"collection": f"eq.{collection}"}
            docs = await self._supabase.select(
                "Documents",
                select="doc_id,title,authors,abstract,filename,tags",
                filters=filters
            )
            
            if not docs:
                logger.warning(f"No documents found in collection: {collection}")
                return []
            
            # Score documents by relevance to search terms
            all_doc_meta: List[DocumentMetadata] = []
            for doc in docs:
                score = self._score_document_relevance(doc, search_terms)
                all_doc_meta.append(DocumentMetadata(
                    doc_id=doc.get("doc_id", ""),
                    title=doc.get("title"),
                    authors=doc.get("authors"),
                    abstract=doc.get("abstract"),
                    filename=doc.get("filename"),
                    tags=doc.get("tags", []) if isinstance(doc.get("tags"), list) else [],
                    relevance_score=score
                ))

            # Sort by relevance descending
            all_doc_meta.sort(key=lambda d: d.relevance_score, reverse=True)

            # Use keyword-matched docs if we have enough; otherwise fall back to top-N
            scored_docs = [d for d in all_doc_meta if d.relevance_score > 0]
            if len(scored_docs) < minimum_documents:
                logger.info(
                    f"Only {len(scored_docs)} keyword-matched docs; "
                    f"falling back to top {minimum_documents} by any score"
                )
                scored_docs = all_doc_meta[:minimum_documents]

            return scored_docs[:max(minimum_documents * 2, 20)]
            
        except Exception as e:
            logger.error(f"Error searching document metadata: {str(e)}")
            return []
    
    def _score_document_relevance(
        self,
        doc: Dict[str, Any],
        search_terms: List[str]
    ) -> float:
        """
        Score a document's relevance to the search terms.
        """
        score = 0.0
        
        # Combine searchable fields
        title = (doc.get("title") or "").lower()
        authors = (doc.get("authors") or "").lower()
        abstract = (doc.get("abstract") or "").lower()
        tags = " ".join(doc.get("tags", [])).lower() if isinstance(doc.get("tags"), list) else ""
        
        for term in search_terms:
            term_lower = term.lower()
            
            # Title matches are most important
            if term_lower in title:
                score += 10.0
            
            # Abstract matches are very important
            if term_lower in abstract:
                score += 5.0
            
            # Author matches
            if term_lower in authors:
                score += 3.0
            
            # Tag matches
            if term_lower in tags:
                score += 2.0
        
        return score
    
    async def _keyword_search_chunks(
        self,
        collection: str,
        query_text: str,
        limit: int = 30,
    ) -> List[Dict[str, Any]]:
        """FTS search on DocumentChunks via Supabase fts_search RPC."""
        try:
            results = await self._supabase.rpc(
                "fts_search",
                {"p_collection": collection, "p_query": query_text, "p_limit": limit},
            )
            return results if isinstance(results, list) else []
        except Exception as e:
            logger.warning(f"FTS search failed (will use vector-only): {e}")
            return []

    async def _retrieve_targeted_chunks(
        self,
        collection: str,
        query_text: str,
        candidate_doc_ids: List[str],
        plan: QueryPlan,
    ) -> List[ChunkResult]:
        """
        Hybrid retrieval: vector search (Qdrant) + keyword FTS (Supabase) run in
        parallel, then merged via Reciprocal Rank Fusion.
        """
        try:
            qvec = await self._embedding_generator.embed_query(query_text)
            await self._vector_store.ensure_collection(collection, len(qvec))
            vector_name = await self._vector_store.get_vector_name(collection)

            vec_hits, fts_results = await asyncio.gather(
                self._vector_store.search(
                    collection=collection,
                    query_vector=qvec,
                    limit=30,
                    doc_id=None,
                    vector_name=vector_name,
                ),
                self._keyword_search_chunks(collection, query_text, limit=30),
            )

            vec_candidates: List[RetrievalCandidate] = []
            for hit in vec_hits:
                payload = hit.payload or {}
                vec_candidates.append(RetrievalCandidate(
                    doc_id=payload.get("doc_id", ""),
                    chunk_index=payload.get("chunk_index", -1),
                    text=payload.get("text", ""),
                    source="vector",
                    raw_score=float(getattr(hit, "score", 0.0)),
                    metadata={
                        "filename": payload.get("filename"),
                        "title": payload.get("title"),
                        "authors": payload.get("authors"),
                    },
                ))

            fts_candidates: List[RetrievalCandidate] = []
            for r in fts_results:
                fts_candidates.append(RetrievalCandidate(
                    doc_id=r.get("doc_id", ""),
                    chunk_index=r.get("chunk_index", -1),
                    text=r.get("chunk_text", ""),
                    source="fts",
                    raw_score=float(r.get("rank", 0.0)),
                    metadata={
                        "filename": None,
                        "title": r.get("title"),
                        "authors": r.get("authors"),
                    },
                ))

            merged = self._hybrid_engine.reciprocal_rank_fusion(
                bm25_candidates=[],
                fts_candidates=fts_candidates,
                vec_candidates=vec_candidates,
            )

            all_chunks: List[ChunkResult] = []
            for c in merged:
                if self._should_include_chunk(c.text, plan):
                    all_chunks.append(ChunkResult(
                        doc_id=c.doc_id,
                        chunk_index=c.chunk_index,
                        text=c.text,
                        score=c.final_score,
                        filename=c.metadata.get("filename"),
                        title=c.metadata.get("title"),
                        authors=c.metadata.get("authors"),
                        section=self._detect_section(c.text),
                    ))

            return all_chunks[:25]

        except Exception as e:
            logger.error(f"Error retrieving chunks: {str(e)}")
            return []
    
    def _should_include_chunk(self, chunk_text: str, plan: QueryPlan) -> bool:
        """
        Determine if a chunk should be included based on section preferences.
        """
        chunk_lower = chunk_text.lower()
        
        # Check avoid sections
        for avoid in plan.avoid_sections:
            if avoid.lower() in chunk_lower[:200]:  # Check first 200 chars
                return False
        
        # If no preferred sections, include all
        if not plan.preferred_sections:
            return True
        
        # Check preferred sections
        for prefer in plan.preferred_sections:
            if prefer.lower() in chunk_lower[:200]:
                return True
        
        # Default: include if not explicitly avoided
        return True
    
    def _detect_section(self, chunk_text: str) -> Optional[str]:
        """
        Detect which section a chunk likely comes from.
        """
        chunk_lower = chunk_text.lower()[:300]
        
        section_markers = {
            "abstract": ["abstract", "summary"],
            "introduction": ["introduction", "background"],
            "methods": ["methods", "methodology", "participants", "procedure"],
            "results": ["results", "findings"],
            "discussion": ["discussion", "interpretation"],
            "conclusion": ["conclusion", "implications", "future research"],
            "references": ["references", "bibliography"],
        }
        
        for section, markers in section_markers.items():
            for marker in markers:
                if marker in chunk_lower:
                    return section
        
        return None
    
    async def _get_total_document_count(self, collection: str) -> int:
        """Get the total number of documents in the collection."""
        try:
            docs = await self._supabase.select(
                "Documents",
                columns="doc_id",
                filters={"collection": f"eq.{collection}"}
            )
            return len(docs) if docs else 0
        except Exception:
            return 0
