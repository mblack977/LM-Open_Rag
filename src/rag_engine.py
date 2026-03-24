import os
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

from qdrant_client.http import models as qm

from src.document_processor import DocumentProcessor
from src.embeddings import EmbeddingGenerator
from src.lm_studio_client import LMStudioClient
from src.vector_store import VectorStore


class RAGEngine:
    def __init__(
        self,
        vector_store: VectorStore,
        embedding_generator: EmbeddingGenerator,
        doc_processor: DocumentProcessor,
        llm_client: Optional[LMStudioClient] = None,
    ):
        self._vector_store = vector_store
        self._embedding_generator = embedding_generator
        self._doc_processor = doc_processor
        self._llm_client = llm_client or LMStudioClient()

    async def add_document(
        self,
        file_path: str,
        collection: str,
        progress_cb: Optional[Callable[[str, int, int, Optional[str]], None]] = None,
        log_cb: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        if log_cb:
            log_cb(f"Processing {file_path}")
        if progress_cb:
            progress_cb("processing", 0, 1, "Extracting + chunking")

        processed = await self._doc_processor.process_document(file_path)
        doc_id = processed["doc_id"]
        chunks = processed["chunks"]
        metadata = processed["metadata"]

        if log_cb:
            log_cb(f"Created {len(chunks)} chunks")

        texts = [c["text"] for c in chunks]

        vectors: List[List[float]] = []
        embed_batch = int(os.getenv("RAG_EMBED_PROGRESS_BATCH") or "8")
        if embed_batch <= 0:
            embed_batch = 8

        total_chunks = len(texts)
        if progress_cb:
            progress_cb("embedding", 0, total_chunks, "Embedding chunks")

        for i in range(0, total_chunks, embed_batch):
            batch = texts[i : i + embed_batch]
            if log_cb:
                log_cb(f"Embedding {min(i + len(batch), total_chunks)}/{total_chunks}")
            batch_vecs = await self._embedding_generator.embed_texts(batch)
            vectors.extend(batch_vecs)
            if progress_cb:
                progress_cb("embedding", min(i + len(batch), total_chunks), total_chunks, None)

        embedding_dim = len(vectors[0]) if vectors else 0

        await self._vector_store.ensure_collection(collection, embedding_dim)
        vector_name = await self._vector_store.get_vector_name(collection)
        existing_size = await self._vector_store.get_vector_size(collection, vector_name)
        if existing_size is not None and existing_size != embedding_dim:
            raise RuntimeError(
                f"Embedding dimension ({embedding_dim}) does not match Qdrant collection '{collection}' "
                f"vector size ({existing_size}) for vector '{vector_name or '<unnamed>'}'. "
                "Use a compatible embedding model or a different collection."
            )

        points: List[qm.PointStruct] = []
        for idx, (chunk, vec) in enumerate(zip(chunks, vectors)):
            payload = {
                "doc_id": doc_id,
                "chunk_index": idx,
                "text": chunk["text"],
                "filename": metadata.get("filename"),
                "file_path": processed.get("file_path"),
                **{f"meta_{k}": v for k, v in chunk.get("metadata", {}).items()},
            }

            point_vector: Any = vec
            if vector_name:
                point_vector = {vector_name: vec}
            points.append(
                qm.PointStruct(
                    id=str(uuid.uuid4()),
                    vector=point_vector,
                    payload=payload,
                )
            )

        upsert_batch = int(os.getenv("QDRANT_UPSERT_BATCH_SIZE") or "64")
        if upsert_batch <= 0:
            upsert_batch = 64

        total_points = len(points)
        if progress_cb:
            progress_cb("upserting", 0, total_points, "Upserting to Qdrant")

        for i in range(0, total_points, upsert_batch):
            batch_points = points[i : i + upsert_batch]
            if log_cb:
                log_cb(f"Upserting {min(i + len(batch_points), total_points)}/{total_points}")
            await self._vector_store.upsert_chunks(collection, batch_points)
            if progress_cb:
                progress_cb("upserting", min(i + len(batch_points), total_points), total_points, None)

        if progress_cb:
            progress_cb("completed", total_points, total_points, "Completed")

        chunk_texts: List[str] = []
        try:
            chunk_texts = [c.get("text") for c in chunks if isinstance(c, dict) and isinstance(c.get("text"), str)]
        except Exception:
            chunk_texts = []

        return {
            "doc_id": doc_id,
            "chunks": len(points),
            "filename": metadata.get("filename"),
            "processed": {
                "metadata": metadata,
                "chunk_texts": chunk_texts,
            },
        }

    async def query(
        self,
        query_text: str,
        collection: str,
        top_k: int = 4,
    ) -> Dict[str, Any]:
        qvec = await self._embedding_generator.embed_query(query_text)
        embedding_dim = len(qvec)

        await self._vector_store.ensure_collection(collection, embedding_dim)
        vector_name = await self._vector_store.get_vector_name(collection)
        existing_size = await self._vector_store.get_vector_size(collection, vector_name)
        if existing_size is not None and existing_size != embedding_dim:
            raise RuntimeError(
                f"Query embedding dimension ({embedding_dim}) does not match Qdrant collection '{collection}' "
                f"vector size ({existing_size}) for vector '{vector_name or '<unnamed>'}'."
            )

        hits = await self._vector_store.search(collection, qvec, limit=top_k, vector_name=vector_name)

        max_chunk_chars = int(os.getenv("RAG_MAX_CONTEXT_CHUNK_CHARS") or "800")
        if max_chunk_chars <= 0:
            max_chunk_chars = 800
        max_total_chars = int(os.getenv("RAG_MAX_CONTEXT_TOTAL_CHARS") or "2500")
        if max_total_chars <= 0:
            max_total_chars = 2500

        context_blocks: List[str] = []
        sources: List[Dict[str, Any]] = []
        total_chars = 0
        for h in hits:
            payload = h.payload or {}
            txt = payload.get("text", "") or ""
            if len(txt) > max_chunk_chars:
                txt = txt[:max_chunk_chars]
            if total_chars + len(txt) > max_total_chars:
                remaining = max_total_chars - total_chars
                if remaining <= 0:
                    break
                txt = txt[:remaining]
            total_chars += len(txt)
            context_blocks.append(txt)
            sources.append(
                {
                    "score": float(h.score),
                    "doc_id": payload.get("doc_id"),
                    "filename": payload.get("filename"),
                    "chunk_index": payload.get("chunk_index"),
                }
            )

        context = "\n\n---\n\n".join(context_blocks)

        system_prompt = os.getenv(
            "RAG_SYSTEM_PROMPT",
            "You are a helpful assistant. Use the provided context to answer. If the answer is not in the context, say you don't know.",
        )

        user_prompt = (
            f"Context:\n{context}\n\n"
            f"Question: {query_text}\n\n"
            "Answer (use the context, be concise, include key details):"
        )

        answer = await self._llm_client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )

        return {"answer": answer, "sources": sources}

    async def list_documents(self, collection: str) -> List[Dict[str, Any]]:
        await self._vector_store.ensure_collection(collection, self._embedding_generator.dimension)
        payloads = await self._vector_store.scroll_all_payload(collection)

        # Deduplicate by doc_id
        by_doc: Dict[str, Dict[str, Any]] = {}
        for p in payloads:
            doc_id = p.get("doc_id")
            if not doc_id:
                continue
            if doc_id not in by_doc:
                by_doc[doc_id] = {
                    "doc_id": doc_id,
                    "filename": p.get("filename"),
                    "file_path": p.get("file_path"),
                }
        return list(by_doc.values())

    async def delete_document(self, collection: str, doc_id: str) -> None:
        await self._vector_store.delete_by_doc_id(collection, doc_id)
