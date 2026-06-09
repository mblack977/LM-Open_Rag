"""
One-shot re-ingestion script for a collection.
Writes to both Qdrant (vectors) and Supabase DocumentChunks (FTS).
Run from the project root: python reingest_collection.py herb_calibration
"""
import asyncio
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
load_dotenv()

from src.document_processor import DocumentProcessor
from src.embeddings import EmbeddingGenerator
from src.supabase_rest import SupabaseRestClient
from src.vector_store import VectorStore
from src.rag_engine import RAGEngine


async def fetch_doc_metadata(supabase: SupabaseRestClient, collection: str, filename: str) -> Dict[str, Any]:
    """Fetch title/authors/notes/tags from Documents table by filename."""
    try:
        rows = await supabase.select(
            "Documents",
            select="doc_id,title,authors,notes,tags",
            filters={"collection": f"eq.{collection}", "filename": f"eq.{filename}"},
            limit=1,
        )
        return rows[0] if rows else {}
    except Exception:
        return {}


async def replace_chunks_in_supabase(
    supabase: SupabaseRestClient,
    collection: str,
    doc_id: str,
    chunk_texts: List[str],
    meta: Dict[str, Any],
) -> None:
    await supabase.delete(
        "DocumentChunks",
        filters={"collection": f"eq.{collection}", "doc_id": f"eq.{doc_id}"},
    )
    rows = []
    for idx, txt in enumerate(chunk_texts):
        if not isinstance(txt, str) or not txt.strip():
            continue
        txt = txt.replace("\x00", "")  # Postgres rejects null bytes in text columns
        rows.append({
            "collection": collection,
            "doc_id": doc_id,
            "chunk_index": idx,
            "chunk_text": txt,
            "title": meta.get("title"),
            "authors": meta.get("authors"),
            "notes": meta.get("notes"),
            "tags": meta.get("tags") if meta.get("tags") is not None else [],
        })
    if rows:
        await supabase.insert("DocumentChunks", rows=rows)


async def reingest(collection: str) -> None:
    uploads_dir = Path("data/uploads") / collection
    if not uploads_dir.exists():
        print(f"ERROR: uploads directory not found: {uploads_dir}")
        sys.exit(1)

    files = sorted(
        list(uploads_dir.glob("*.pdf"))
        + list(uploads_dir.glob("*.txt"))
        + list(uploads_dir.glob("*.md"))
    )
    if not files:
        print("No files found to ingest.")
        return

    print(f"Found {len(files)} files in {uploads_dir}")
    print(f"Embedding model: ", end="", flush=True)

    eg = EmbeddingGenerator()
    # Report which embedding backend is active
    if eg._ollama_embedding_model:
        print(f"Ollama / {eg._ollama_embedding_model}")
    elif eg._lm_embedding_model:
        print(f"LM Studio / {eg._lm_embedding_model}")
    else:
        print(f"local SentenceTransformer / {eg._model_name}")

    vs = VectorStore()
    dp = DocumentProcessor()
    sb = SupabaseRestClient()
    engine = RAGEngine(vector_store=vs, embedding_generator=eg, doc_processor=dp)

    ok, failed = 0, 0
    total_start = time.time()

    for i, file_path in enumerate(files, 1):
        name = file_path.name
        print(f"[{i}/{len(files)}] {name} ... ", end="", flush=True)
        t0 = time.time()
        try:
            result = await engine.add_document(str(file_path), collection=collection)
            doc_id = result["doc_id"]
            chunk_texts = result.get("processed", {}).get("chunk_texts", [])

            # Also write chunks to Supabase for FTS
            meta = await fetch_doc_metadata(sb, collection, name)
            await replace_chunks_in_supabase(sb, collection, doc_id, chunk_texts, meta)

            elapsed = time.time() - t0
            print(f"OK  {result['chunks']} chunks  ({elapsed:.1f}s)")
            ok += 1
        except Exception as e:
            elapsed = time.time() - t0
            print(f"FAILED ({elapsed:.1f}s): {e}")
            failed += 1

    total = time.time() - total_start
    print(f"\nDone in {total:.0f}s — {ok} ingested, {failed} failed")

    if failed == 0:
        # Verify
        qdrant_cols = await vs.list_collections()
        chunks_check = await sb.select("DocumentChunks", select="doc_id", filters={"collection": f"eq.{collection}"})
        print(f"Qdrant collections: {qdrant_cols}")
        print(f"DocumentChunks rows: {len(chunks_check)}")


if __name__ == "__main__":
    col = sys.argv[1] if len(sys.argv) > 1 else "herb_calibration"
    asyncio.run(reingest(col))
