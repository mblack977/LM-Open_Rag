from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
import uvicorn
import os
from pathlib import Path
import json
import asyncio
from typing import Any, Dict, List, Optional, Tuple
import logging
import time
import uuid


# Import our RAG modules
from src.rag_engine import RAGEngine
from src.document_processor import DocumentProcessor
from src.vector_store import VectorStore
from src.embeddings import EmbeddingGenerator
from src.lm_studio_client import LMStudioClient
from src.supabase_rest import SupabaseRestClient, SupabaseRestError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Local RAG System", description="A locally hosted Retrieval-Augmented Generation system")

# Setup directories
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"

# Create directories if they don't exist
for dir_path in [STATIC_DIR, TEMPLATES_DIR, DATA_DIR, UPLOADS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# Mount static files and setup templates
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Initialize RAG components
vector_store = VectorStore(data_dir=DATA_DIR)
embedding_generator = EmbeddingGenerator()
doc_processor = DocumentProcessor()
llm_client = LMStudioClient()
rag_engine = RAGEngine(vector_store, embedding_generator, doc_processor, llm_client=llm_client)


supabase: Optional[SupabaseRestClient] = None
try:
    supabase = SupabaseRestClient()
except SupabaseRestError as e:
    logger.warning(f"Supabase disabled: {str(e)}")


JOBS: Dict[str, Dict[str, Any]] = {}


def _job_log(job_id: str, message: str) -> None:
    job = JOBS.get(job_id)
    if not job:
        return
    logs = job.get("logs")
    if not isinstance(logs, list):
        logs = []
        job["logs"] = logs
    logs.append(message)
    if len(logs) > 500:
        job["logs"] = logs[-500:]


def _job_progress(job_id: str, stage: str, current: int, total: int, message: Optional[str] = None) -> None:
    job = JOBS.get(job_id)
    if not job:
        return
    job["stage"] = stage
    job["current"] = int(current)
    job["total"] = int(total)
    if isinstance(message, str) and message.strip():
        job["message"] = message
        _job_log(job_id, message)


async def _supabase_upsert_document(collection: str, doc: Dict[str, Any]) -> None:
    if not supabase:
        return

    doc_id = doc.get("doc_id")
    if not isinstance(doc_id, str) or not doc_id.strip():
        return

    existing = await supabase.select(
        "Documents",
        select="doc_id",
        filters={
            "collection": f"eq.{collection}",
            "doc_id": f"eq.{doc_id}",
        },
        limit=1,
    )

    row = {
        "collection": collection,
        "doc_id": doc_id,
        "filename": doc.get("filename"),
        "file_path": doc.get("file_path"),
        "file_size": doc.get("file_size"),
        "created_time": doc.get("created_time"),
        "modified_time": doc.get("modified_time"),
        "title": doc.get("title") or doc.get("filename"),
        "authors": doc.get("authors"),
        "abstract": doc.get("abstract"),
        "notes": doc.get("notes"),
        "tags": doc.get("tags"),
    }

    if existing:
        patch = {k: v for k, v in row.items() if k not in {"collection", "doc_id"} and v is not None}
        if patch:
            await supabase.update(
                "Documents",
                patch=patch,
                filters={
                    "collection": f"eq.{collection}",
                    "doc_id": f"eq.{doc_id}",
                },
            )
        return

    await supabase.insert(
        "Documents",
        rows=[
            {
                **row,
                "authors": row.get("authors") or "",
                "abstract": row.get("abstract") or "",
                "notes": row.get("notes") or "",
                "tags": row.get("tags") if row.get("tags") is not None else [],
            }
        ],
    )


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default


async def _retrieve_fts(collection: str, query_text: str, limit: int) -> List[Dict[str, Any]]:
    if not supabase:
        return []

    payload = {
        "p_collection": collection,
        "p_query": query_text,
        "p_limit": int(limit),
        "p_doc_id": None,
    }
    rows = await supabase.rpc("fts_search", payload=payload)
    if not isinstance(rows, list):
        return []

    out: List[Dict[str, Any]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        doc_id = r.get("doc_id")
        chunk_index = r.get("chunk_index")
        chunk_text = r.get("chunk_text")
        if not isinstance(doc_id, str) or not isinstance(chunk_text, str):
            continue
        out.append(
            {
                "source": "fts",
                "doc_id": doc_id,
                "chunk_index": _safe_int(chunk_index, -1),
                "text": chunk_text,
                "rank": _safe_float(r.get("rank"), 0.0),
                "title": r.get("title"),
                "authors": r.get("authors"),
                "tags": r.get("tags"),
                "notes": r.get("notes"),
            }
        )
    return out


async def _retrieve_vector(collection: str, query_text: str, limit: int) -> List[Dict[str, Any]]:
    qvec = await embedding_generator.embed_query(query_text)
    await vector_store.ensure_collection(collection, len(qvec))
    vector_name = await vector_store.get_vector_name(collection)
    hits = await vector_store.search(collection, qvec, limit=int(limit), vector_name=vector_name)

    out: List[Dict[str, Any]] = []
    for h in hits:
        payload = h.payload or {}
        if not isinstance(payload, dict):
            continue
        doc_id = payload.get("doc_id")
        txt = payload.get("text")
        if not isinstance(doc_id, str) or not isinstance(txt, str):
            continue
        out.append(
            {
                "source": "vector",
                "doc_id": doc_id,
                "chunk_index": _safe_int(payload.get("chunk_index"), -1),
                "text": txt,
                "score": _safe_float(getattr(h, "score", None), 0.0),
                "filename": payload.get("filename"),
            }
        )
    return out


def _rrf_merge(
    fts: List[Dict[str, Any]],
    vec: List[Dict[str, Any]],
    k: int = 60,
) -> List[Dict[str, Any]]:
    merged: Dict[Tuple[str, int], Dict[str, Any]] = {}

    def add_list(items: List[Dict[str, Any]], label: str) -> None:
        for rank0, item in enumerate(items):
            doc_id = item.get("doc_id")
            chunk_index = item.get("chunk_index")
            if not isinstance(doc_id, str):
                continue
            try:
                ci = int(chunk_index)
            except Exception:
                ci = -1
            key = (doc_id, ci)
            if key not in merged:
                merged[key] = dict(item)
                merged[key]["rrf_score"] = 0.0
                merged[key]["sources"] = []

            merged[key]["rrf_score"] = float(merged[key].get("rrf_score") or 0.0) + (1.0 / float(k + rank0 + 1))
            srcs = merged[key].get("sources")
            if isinstance(srcs, list):
                srcs.append(label)

    add_list(fts, "fts")
    add_list(vec, "vector")

    out = list(merged.values())
    out.sort(key=lambda x: float(x.get("rrf_score") or 0.0), reverse=True)
    return out


async def _retrieve_candidates(
    collection: str,
    query_text: str,
    mode: str,
    top_k: int,
    fts_limit: int,
    vec_limit: int,
) -> List[Dict[str, Any]]:
    mode = (mode or "").strip().lower()
    if mode not in {"fts", "vector", "hybrid"}:
        mode = "hybrid"

    if mode == "fts":
        return (await _retrieve_fts(collection, query_text, limit=top_k))[:top_k]
    if mode == "vector":
        return (await _retrieve_vector(collection, query_text, limit=top_k))[:top_k]

    fts_hits = await _retrieve_fts(collection, query_text, limit=fts_limit)
    vec_hits = await _retrieve_vector(collection, query_text, limit=vec_limit)
    merged = _rrf_merge(fts_hits, vec_hits)
    return merged[:top_k]


async def _answer_with_candidates(query_text: str, collection: str, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    max_chunk_chars = int(os.getenv("RAG_MAX_CONTEXT_CHUNK_CHARS") or "800")
    if max_chunk_chars <= 0:
        max_chunk_chars = 800
    max_total_chars = int(os.getenv("RAG_MAX_CONTEXT_TOTAL_CHARS") or "2500")
    if max_total_chars <= 0:
        max_total_chars = 2500

    context_blocks: List[str] = []
    sources: List[Dict[str, Any]] = []
    total_chars = 0
    for c in candidates:
        txt = (c.get("text") or "")
        if not isinstance(txt, str) or not txt:
            continue
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
                "doc_id": c.get("doc_id"),
                "chunk_index": c.get("chunk_index"),
                "source": c.get("source"),
                "rrf_score": c.get("rrf_score"),
                "rank": c.get("rank"),
                "score": c.get("score"),
                "filename": c.get("filename"),
                "title": c.get("title"),
                "authors": c.get("authors"),
                "tags": c.get("tags"),
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

    answer = await llm_client.chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )
    return {"answer": answer, "sources": sources}

    row = {
        "collection": collection,
        "doc_id": doc_id,
        "filename": doc.get("filename"),
        "file_path": doc.get("file_path"),
        "file_size": doc.get("file_size"),
        "created_time": doc.get("created_time"),
        "modified_time": doc.get("modified_time"),
        "title": doc.get("title") or doc.get("filename"),
        "authors": doc.get("authors"),
        "abstract": doc.get("abstract"),
        "notes": doc.get("notes"),
        "tags": doc.get("tags"),
    }

    if existing:
        patch = {k: v for k, v in row.items() if k not in {"collection", "doc_id"} and v is not None}
        if patch:
            await supabase.update(
                "Documents",
                patch=patch,
                filters={
                    "collection": f"eq.{collection}",
                    "doc_id": f"eq.{doc_id}",
                },
            )
        return

    await supabase.insert(
        "Documents",
        rows=[
            {
                **row,
                "authors": row.get("authors") or "",
                "abstract": row.get("abstract") or "",
                "notes": row.get("notes") or "",
                "tags": row.get("tags") if row.get("tags") is not None else [],
            }
        ],
    )


async def _supabase_delete_document(collection: str, doc_id: str) -> None:
    if not supabase:
        return
    await supabase.delete(
        "Documents",
        filters={
            "collection": f"eq.{collection}",
            "doc_id": f"eq.{doc_id}",
        },
    )


async def _supabase_replace_chunks(
    collection: str,
    doc_id: str,
    chunk_texts: List[str],
    title: Optional[str],
    authors: Optional[str],
    notes: Optional[str],
    tags: Any,
) -> None:
    if not supabase:
        return
    if not isinstance(doc_id, str) or not doc_id.strip():
        return

    await supabase.delete(
        "DocumentChunks",
        filters={
            "collection": f"eq.{collection}",
            "doc_id": f"eq.{doc_id}",
        },
    )

    rows: List[Dict[str, Any]] = []
    for idx, txt in enumerate(chunk_texts):
        if not isinstance(txt, str) or not txt.strip():
            continue
        rows.append(
            {
                "collection": collection,
                "doc_id": doc_id,
                "chunk_index": int(idx),
                "chunk_text": txt,
                "title": title,
                "authors": authors,
                "notes": notes,
                "tags": tags if tags is not None else [],
            }
        )

    if rows:
        await supabase.insert("DocumentChunks", rows=rows)


async def _process_document_only(file_path: Path) -> Dict[str, Any]:
    processed = await doc_processor.process_document(str(file_path))
    doc_id = processed.get("doc_id")
    metadata = processed.get("metadata") or {}
    chunks = processed.get("chunks") or []
    chunk_texts: List[str] = []
    try:
        chunk_texts = [c.get("text") for c in chunks if isinstance(c, dict) and isinstance(c.get("text"), str)]
    except Exception:
        chunk_texts = []

    return {
        "doc_id": doc_id,
        "filename": metadata.get("filename") or file_path.name,
        "processed": {"metadata": metadata, "chunk_texts": chunk_texts},
        "vector_status": "skipped",
    }

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the main web interface"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/collections")
async def list_collections():
    try:
        collections = await vector_store.list_collections()
        return {"status": "success", "collections": collections}
    except Exception as e:
        logger.error(f"Error listing collections: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing collections: {str(e)}")


@app.get("/v1/models")
async def openai_list_models():
    try:
        collections = await vector_store.list_collections()
        models = [{"id": f"rag-{c}", "object": "model", "owned_by": "local"} for c in collections]
        return {"object": "list", "data": models}
    except Exception as e:
        logger.error(f"Error listing OpenAI models: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing models: {str(e)}")


def _collection_from_model(model: str) -> str:
    if not model:
        raise HTTPException(status_code=400, detail="model is required")
    if not model.startswith("rag-"):
        raise HTTPException(status_code=400, detail="model must be in the form rag-<collection>")
    collection = model[len("rag-"):].strip()
    if not collection:
        raise HTTPException(status_code=400, detail="collection part of model is empty")
    return collection


@app.post("/v1/chat/completions")
async def openai_chat_completions(payload: Dict[str, Any]):
    try:
        model = payload.get("model")
        collection = _collection_from_model(model)

        messages = payload.get("messages") or []
        if not isinstance(messages, list) or not messages:
            raise HTTPException(status_code=400, detail="messages must be a non-empty list")

        # Use the latest user message as the retrieval query.
        user_text = None
        for m in reversed(messages):
            if isinstance(m, dict) and m.get("role") == "user":
                user_text = m.get("content")
                break
        if not user_text or not isinstance(user_text, str):
            raise HTTPException(status_code=400, detail="No user message content found")

        stream = bool(payload.get("stream", False))

        mode = payload.get("retrieval_mode") or payload.get("mode") or os.getenv("RETRIEVAL_MODE") or "hybrid"
        top_k = _safe_int(payload.get("top_k"), int(os.getenv("RETRIEVAL_TOP_K") or "6"))
        fts_limit = _safe_int(payload.get("fts_limit"), int(os.getenv("RETRIEVAL_FTS_LIMIT") or "30"))
        vec_limit = _safe_int(payload.get("vec_limit"), int(os.getenv("RETRIEVAL_VEC_LIMIT") or "30"))

        candidates = await _retrieve_candidates(
            collection=collection,
            query_text=user_text,
            mode=str(mode),
            top_k=top_k,
            fts_limit=fts_limit,
            vec_limit=vec_limit,
        )
        rag_result = await _answer_with_candidates(user_text, collection=collection, candidates=candidates)
        answer = rag_result.get("answer", "")

        session_id = payload.get("session_id")
        if supabase and isinstance(session_id, str) and session_id.strip():
            try:
                await supabase.insert(
                    "ChatMessages",
                    rows=[
                        {"session_id": session_id, "role": "user", "content": user_text},
                        {"session_id": session_id, "role": "assistant", "content": answer},
                    ],
                )
            except Exception as e:
                logger.warning(f"Failed to persist chat messages: {str(e)}")

        created = int(time.time())
        response_id = f"chatcmpl-{uuid.uuid4().hex}"

        if not stream:
            return {
                "id": response_id,
                "object": "chat.completion",
                "created": created,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": answer},
                        "finish_reason": "stop",
                    }
                ],
            }

        async def event_stream():
            # Initial chunk
            init = {
                "id": response_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
            }
            yield f"data: {json.dumps(init)}\n\n"

            # Content chunk (single chunk for now)
            chunk = {
                "id": response_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{"index": 0, "delta": {"content": answer}, "finish_reason": None}],
            }
            yield f"data: {json.dumps(chunk)}\n\n"

            # Final
            done = {
                "id": response_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }
            yield f"data: {json.dumps(done)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in OpenAI chat completions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating completion: {str(e)}")

@app.post("/upload")
async def upload_document(collection: str = Form(...), file: UploadFile = File(...)):
    """Upload and process a document"""
    try:
        # Save uploaded file
        safe_collection = collection.strip()
        if not safe_collection:
            raise HTTPException(status_code=400, detail="Collection is required")

        collection_dir = UPLOADS_DIR / safe_collection
        collection_dir.mkdir(parents=True, exist_ok=True)

        file_path = collection_dir / file.filename
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        result: Dict[str, Any]
        ingest_warning: Optional[str] = None
        try:
            result = await rag_engine.add_document(str(file_path), collection=safe_collection)
            result["vector_status"] = "ok"
        except Exception as e:
            ingest_warning = str(e)
            logger.warning(f"Vector ingestion failed (continuing with Supabase chunks only): {str(e)}")
            result = await _process_document_only(file_path)
            result["vector_status"] = "failed"

        try:
            processed = result.get("processed") or {}
            meta = processed.get("metadata") if isinstance(processed, dict) else {}
            chunk_texts = processed.get("chunk_texts") if isinstance(processed, dict) else []

            await _supabase_upsert_document(
                safe_collection,
                {
                    "doc_id": result.get("doc_id"),
                    "filename": result.get("filename") or file.filename,
                    "file_path": str(file_path),
                    "file_size": file_path.stat().st_size,
                    "created_time": meta.get("created_time") if isinstance(meta, dict) else None,
                    "modified_time": meta.get("modified_time") if isinstance(meta, dict) else None,
                    "title": (meta.get("filename") if isinstance(meta, dict) else None) or (result.get("filename") or file.filename),
                    "authors": "",
                    "abstract": "",
                    "notes": "",
                    "tags": [],
                },
            )

            if isinstance(chunk_texts, list):
                await _supabase_replace_chunks(
                    collection=safe_collection,
                    doc_id=str(result.get("doc_id") or ""),
                    chunk_texts=[c for c in chunk_texts if isinstance(c, str)],
                    title=(result.get("filename") or file.filename),
                    authors="",
                    notes="",
                    tags=[],
                )
        except Exception as e:
            logger.warning(f"Failed to upsert Supabase document/chunks: {str(e)}")
        
        return {
            "status": "success",
            "message": f"Document {file.filename} uploaded and processed successfully",
            "result": result,
            "warning": ingest_warning,
        }
    
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}")


@app.post("/upload_async")
async def upload_document_async(collection: str = Form(...), file: UploadFile = File(...)):
    """Upload and process a document asynchronously with progress reporting"""
    try:
        safe_collection = collection.strip()
        if not safe_collection:
            raise HTTPException(status_code=400, detail="Collection is required")

        collection_dir = UPLOADS_DIR / safe_collection
        collection_dir.mkdir(parents=True, exist_ok=True)

        file_path = collection_dir / file.filename
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        job_id = f"job-{uuid.uuid4().hex}"
        JOBS[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "stage": "queued",
            "current": 0,
            "total": 0,
            "message": "Queued",
            "logs": [],
            "result": None,
            "error": None,
            "created_at": time.time(),
            "collection": safe_collection,
            "filename": file.filename,
        }
        _job_log(job_id, f"Saved upload to {str(file_path)}")

        async def run_job() -> None:
            try:
                job = JOBS.get(job_id)
                if not job:
                    return
                job["status"] = "running"
                _job_progress(job_id, "processing", 0, 1, "Processing document")

                try:
                    result = await rag_engine.add_document(
                        str(file_path),
                        collection=safe_collection,
                        progress_cb=lambda stage, current, total, msg=None: _job_progress(job_id, stage, current, total, msg),
                        log_cb=lambda msg: _job_log(job_id, msg),
                    )
                    result["vector_status"] = "ok"
                except Exception as e:
                    _job_log(job_id, f"Vector ingestion failed (continuing with Supabase chunks only): {str(e)}")
                    result = await _process_document_only(file_path)
                    result["vector_status"] = "failed"

                try:
                    processed = result.get("processed") or {}
                    meta = processed.get("metadata") if isinstance(processed, dict) else {}
                    chunk_texts = processed.get("chunk_texts") if isinstance(processed, dict) else []

                    await _supabase_upsert_document(
                        safe_collection,
                        {
                            "doc_id": result.get("doc_id"),
                            "filename": result.get("filename") or file.filename,
                            "file_path": str(file_path),
                            "file_size": file_path.stat().st_size,
                            "created_time": meta.get("created_time") if isinstance(meta, dict) else None,
                            "modified_time": meta.get("modified_time") if isinstance(meta, dict) else None,
                            "title": (meta.get("filename") if isinstance(meta, dict) else None)
                            or (result.get("filename") or file.filename),
                            "authors": "",
                            "abstract": "",
                            "notes": "",
                            "tags": [],
                        },
                    )

                    if isinstance(chunk_texts, list):
                        await _supabase_replace_chunks(
                            collection=safe_collection,
                            doc_id=str(result.get("doc_id") or ""),
                            chunk_texts=[c for c in chunk_texts if isinstance(c, str)],
                            title=(result.get("filename") or file.filename),
                            authors="",
                            notes="",
                            tags=[],
                        )
                except Exception as e:
                    _job_log(job_id, f"Supabase metadata upsert failed: {str(e)}")
                job = JOBS.get(job_id)
                if not job:
                    return
                job["status"] = "completed"
                job["stage"] = "completed"
                job["result"] = result
                job["message"] = "Completed"
                _job_log(job_id, "Completed")
            except Exception as e:
                job = JOBS.get(job_id)
                if not job:
                    return
                job["status"] = "failed"
                job["stage"] = "failed"
                job["error"] = str(e)
                job["message"] = f"Failed: {str(e)}"
                _job_log(job_id, f"Failed: {str(e)}")

        asyncio.create_task(run_job())

        return {"status": "accepted", "job_id": job_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading document async: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}")


@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.post("/query")
async def query_documents(
    collection: str = Form(...),
    query: str = Form(...),
    mode: str = Form("hybrid"),
    top_k: int = Form(6),
    fts_limit: int = Form(30),
    vec_limit: int = Form(30),
    retrieve_only: bool = Form(False),
):
    """Query the RAG system"""
    try:
        safe_collection = collection.strip()
        if not safe_collection:
            raise HTTPException(status_code=400, detail="Collection is required")

        candidates = await _retrieve_candidates(
            collection=safe_collection,
            query_text=query,
            mode=mode,
            top_k=int(top_k),
            fts_limit=int(fts_limit),
            vec_limit=int(vec_limit),
        )

        if retrieve_only:
            return {"status": "success", "mode": (mode or "hybrid"), "candidates": candidates}

        try:
            response = await _answer_with_candidates(query, collection=safe_collection, candidates=candidates)
        except Exception as e:
            raise HTTPException(
                status_code=502,
                detail=(
                    "Retrieved candidates successfully, but failed to generate an answer. "
                    "Check LM Studio is running and LM_STUDIO_BASE_URL/LM_STUDIO_MODEL are correct. "
                    f"Error: {str(e)}"
                ),
            )
        return {"status": "success", "response": response, "mode": (mode or "hybrid")}
    
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

@app.get("/documents")
async def list_documents(collection: str):
    """List all processed documents"""
    try:
        safe_collection = collection.strip()
        if not safe_collection:
            raise HTTPException(status_code=400, detail="Collection is required")

        if supabase:
            docs = await supabase.select(
                "Documents",
                select="doc_id,collection,filename,file_path,file_size,title,authors,abstract,notes,tags,created_time,modified_time,created_at,updated_at",
                filters={"collection": f"eq.{safe_collection}"},
                order="created_at.desc",
            )
            return {"status": "success", "documents": docs}

        documents = await rag_engine.list_documents(collection=safe_collection)
        return {"status": "success", "documents": documents}
    
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing documents: {str(e)}")

@app.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, collection: str):
    """Delete a document from the system"""
    try:
        safe_collection = collection.strip()
        if not safe_collection:
            raise HTTPException(status_code=400, detail="Collection is required")

        await rag_engine.delete_document(collection=safe_collection, doc_id=doc_id)
        try:
            await _supabase_delete_document(safe_collection, doc_id)
        except Exception as e:
            logger.warning(f"Failed to delete Supabase document metadata: {str(e)}")
        return {"status": "success", "message": f"Document {doc_id} deleted successfully"}
    
    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting document: {str(e)}")


@app.patch("/documents/{doc_id}")
async def update_document_metadata(doc_id: str, collection: str, payload: Dict[str, Any]):
    try:
        safe_collection = collection.strip()
        if not safe_collection:
            raise HTTPException(status_code=400, detail="Collection is required")
        if not supabase:
            raise HTTPException(status_code=503, detail="Supabase is not configured")

        allowed = {"title", "authors", "abstract", "notes", "tags"}
        patch = {k: v for k, v in payload.items() if k in allowed}
        if not patch:
            raise HTTPException(status_code=400, detail="No updatable fields provided")

        rows = await supabase.update(
            "Documents",
            patch=patch,
            filters={
                "collection": f"eq.{safe_collection}",
                "doc_id": f"eq.{doc_id}",
            },
        )
        return {"status": "success", "document": rows[0] if rows else None}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating document metadata: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating document metadata: {str(e)}")


@app.get("/chat/sessions")
async def list_chat_sessions(collection: str):
    try:
        safe_collection = collection.strip()
        if not safe_collection:
            raise HTTPException(status_code=400, detail="Collection is required")
        if not supabase:
            raise HTTPException(status_code=503, detail="Supabase is not configured")

        rows = await supabase.select(
            "ChatSessions",
            select="id,collection,name,created_at,updated_at",
            filters={"collection": f"eq.{safe_collection}"},
            order="updated_at.desc",
        )
        return {"status": "success", "sessions": rows}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing chat sessions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing chat sessions: {str(e)}")


@app.post("/chat/sessions")
async def create_chat_session(collection: str = Form(...), name: str = Form(...)):
    try:
        safe_collection = collection.strip()
        safe_name = name.strip()
        if not safe_collection:
            raise HTTPException(status_code=400, detail="Collection is required")
        if not safe_name:
            raise HTTPException(status_code=400, detail="name is required")
        if not supabase:
            raise HTTPException(status_code=503, detail="Supabase is not configured")

        rows = await supabase.insert(
            "ChatSessions",
            rows=[{"collection": safe_collection, "name": safe_name}],
        )
        return {"status": "success", "session": rows[0] if rows else None}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating chat session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating chat session: {str(e)}")


@app.get("/chat/sessions/{session_id}/messages")
async def list_chat_messages(session_id: str):
    try:
        if not supabase:
            raise HTTPException(status_code=503, detail="Supabase is not configured")

        rows = await supabase.select(
            "ChatMessages",
            select="id,session_id,role,content,created_at",
            filters={"session_id": f"eq.{session_id}"},
            order="created_at.asc",
        )
        return {"status": "success", "messages": rows}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing chat messages: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing chat messages: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "Local RAG system is running"}

if __name__ == "__main__":
    reload_enabled = (os.getenv("UVICORN_RELOAD") or "").strip() == "1"
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=reload_enabled)
