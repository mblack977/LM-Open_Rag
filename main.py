from fastapi import FastAPI, File, UploadFile, HTTPException, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
import uvicorn
import os
import json
import httpx
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
import json
import asyncio
from typing import Any, Dict, List, Optional, Tuple
import logging
import time
import uuid


# Import our RAG modules
from src.provider_config import ProviderSettings, current_settings as _default_settings
from src.rag_engine import RAGEngine
from src.document_processor import DocumentProcessor
from src.vector_store import VectorStore
from src.embeddings import EmbeddingGenerator
from src.lm_studio_client import LMStudioClient
from src.supabase_rest import SupabaseRestClient, SupabaseRestError
from src.collection_manager import CollectionManager
from src.db_collection_manager import DBCollectionManager
from src.retrieval_api import RetrievalAPI
from src.retrieval_profile_manager import RetrievalProfileManager
from src.hybrid_retrieval import HybridRetrievalEngine
from src.retrieval_profiles import RetrievalProfile
from src.chat_manager import ChatManager
from src.document_manager import DocumentManager
from src.query_tracker import QueryTracker
from src.evaluation_manager import EvaluationManager
from src.analytics_manager import AnalyticsManager
from src.query_planner import QueryPlanner
from src.collection_retriever import CollectionRetriever
from src.response_generator import ResponseGenerator
from src.nlp_analyzer import NLPAnalyzer
from src.llm_router import LLMRouter
from src.crossref_enricher import CrossRefEnricher

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
COLLECTIONS_DIR = DATA_DIR / "collections"
COLLECTION_IMAGES_DIR = DATA_DIR / "collection_images"
HERB_FILES_DIR = Path(os.getenv("HERB_FILES_DIR", r"C:\Herb Project"))

# Create directories if they don't exist
for dir_path in [STATIC_DIR, TEMPLATES_DIR, DATA_DIR, UPLOADS_DIR, COLLECTIONS_DIR, COLLECTION_IMAGES_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# Mount static files and setup templates
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/collection-images", StaticFiles(directory=COLLECTION_IMAGES_DIR), name="collection-images")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Initialize RAG components
vector_store = VectorStore(data_dir=DATA_DIR)
embedding_generator = EmbeddingGenerator()
doc_processor = DocumentProcessor()
llm_client = LMStudioClient()
rag_engine = RAGEngine(vector_store, embedding_generator, doc_processor, llm_client=llm_client)
collection_manager = CollectionManager(collections_dir=COLLECTIONS_DIR)


supabase: Optional[SupabaseRestClient] = None
try:
    supabase = SupabaseRestClient()
    logger.info("Supabase client initialized successfully")
except SupabaseRestError as e:
    logger.warning(f"Supabase disabled (SupabaseRestError): {str(e)}")
except Exception as e:
    logger.warning(f"Supabase disabled (unexpected error): {type(e).__name__}: {str(e)}")

retrieval_api = RetrievalAPI(supabase)
profile_manager = RetrievalProfileManager(supabase)
hybrid_engine = HybridRetrievalEngine()
chat_manager = ChatManager(supabase) if supabase else None
document_manager = DocumentManager(supabase) if supabase else None
query_tracker = QueryTracker(supabase) if supabase else None
evaluation_manager = EvaluationManager(supabase) if supabase else None
analytics_manager = AnalyticsManager(supabase) if supabase else None
db_collection_manager = DBCollectionManager(supabase, COLLECTION_IMAGES_DIR) if supabase else None

query_planner = QueryPlanner(llm_client=None)
collection_retriever = CollectionRetriever(supabase, vector_store, embedding_generator) if supabase else None
crossref_enricher = CrossRefEnricher(supabase, os.getenv("CROSSREF_MAILTO", "")) if supabase else None
response_generator = ResponseGenerator(llm_client)

_s = _default_settings
fast_llm_client = LMStudioClient(
    base_url=_s.fast_base_url,
    api_key=_s.fast_api_key,
    model=_s.fast_model,
    timeout_seconds=_s.fast_timeout,
)
large_llm_client = LMStudioClient(
    base_url=_s.large_base_url,
    api_key=_s.large_api_key,
    model=_s.large_model,
    timeout_seconds=_s.large_timeout,
)
nlp_analyzer = NLPAnalyzer()
llm_router = LLMRouter(fast_llm_client, large_llm_client)

JOBS: Dict[str, Dict[str, Any]] = {}
SETTINGS_FILE = DATA_DIR / "settings.json"

# ── Provider settings (runtime-mutable) ──────────────────────────────────────
provider_settings: ProviderSettings = _default_settings


def _load_settings_from_file() -> None:
    """Overlay file-persisted settings on top of env defaults."""
    global provider_settings
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text())
            for field in ProviderSettings.__dataclass_fields__:
                if field in data and data[field] is not None:
                    setattr(provider_settings, field, data[field])
        except Exception as e:
            logger.warning(f"Could not load settings file: {e}")


def _save_settings_to_file(settings: ProviderSettings) -> None:
    import dataclasses
    SETTINGS_FILE.write_text(json.dumps(dataclasses.asdict(settings), indent=2))


def _apply_provider_settings(settings: ProviderSettings) -> None:
    """Reinitialise the global LLM and embedding clients from updated settings."""
    global llm_client, embedding_generator, rag_engine
    from src.lm_studio_client import LMStudioClient
    from src.embeddings import EmbeddingGenerator

    # Update env vars so existing constructors pick them up
    if settings.chat_provider == "openai":
        os.environ["LM_STUDIO_BASE_URL"] = settings.chat_base_url or "https://api.openai.com/v1"
        os.environ["LM_STUDIO_API_KEY"] = settings.chat_api_key or ""
        os.environ["LM_STUDIO_MODEL"] = settings.chat_model or "gpt-4o-mini"
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ["OPENAI_API_KEY"] = settings.chat_api_key or ""
    elif settings.chat_provider == "ollama":
        os.environ["LM_STUDIO_BASE_URL"] = (settings.chat_base_url or "http://localhost:11434") + "/v1"
        os.environ["LM_STUDIO_API_KEY"] = "ollama"
        os.environ["LM_STUDIO_MODEL"] = settings.chat_model or ""
    else:  # lm_studio
        os.environ["LM_STUDIO_BASE_URL"] = settings.chat_base_url or "http://localhost:1234/v1"
        os.environ["LM_STUDIO_API_KEY"] = settings.chat_api_key or "lm-studio"
        os.environ["LM_STUDIO_MODEL"] = settings.chat_model or ""

    if settings.embedding_provider == "openai":
        os.environ.pop("OLLAMA_EMBEDDING_MODEL", None)
        os.environ.pop("LM_STUDIO_EMBEDDING_MODEL", None)
        os.environ["OPENAI_EMBEDDING_MODEL"] = settings.embedding_model or "text-embedding-3-small"
        os.environ["LM_STUDIO_BASE_URL"] = settings.embedding_base_url or "https://api.openai.com/v1"
        os.environ["LM_STUDIO_API_KEY"] = settings.embedding_api_key or ""
        os.environ["LM_STUDIO_EMBEDDING_MODEL"] = settings.embedding_model or "text-embedding-3-small"
    elif settings.embedding_provider == "ollama":
        os.environ.pop("LM_STUDIO_EMBEDDING_MODEL", None)
        os.environ["OLLAMA_BASE_URL"] = settings.embedding_base_url or "http://localhost:11434"
        os.environ["OLLAMA_EMBEDDING_MODEL"] = settings.embedding_model or "mxbai-embed-large"
    elif settings.embedding_provider == "lm_studio":
        os.environ.pop("OLLAMA_EMBEDDING_MODEL", None)
        os.environ["LM_STUDIO_EMBEDDING_MODEL"] = settings.embedding_model or ""
    else:  # local
        os.environ.pop("OLLAMA_EMBEDDING_MODEL", None)
        os.environ.pop("LM_STUDIO_EMBEDDING_MODEL", None)

    llm_client = LMStudioClient()
    embedding_generator = EmbeddingGenerator()
    rag_engine = RAGEngine(vector_store, embedding_generator, doc_processor, llm_client=llm_client)
    logger.info(f"Provider settings applied: chat={settings.chat_provider}, embedding={settings.embedding_provider}")


# Load persisted settings at startup
_load_settings_from_file()


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


async def _supabase_upsert_document(collection: str, doc: Dict[str, Any]) -> Optional[int]:
    """Upsert document and return the document ID"""
    if not supabase:
        return None

    doc_id = doc.get("doc_id")
    if not isinstance(doc_id, str) or not doc_id.strip():
        return None

    existing = await supabase.select(
        "Documents",
        select="id,doc_id",
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
        "pdf_attached": True if doc.get("file_path") else False,
        "ingestion_status": "processing",
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
        return existing[0].get("id")

    result = await supabase.insert(
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
    
    if result and len(result) > 0:
        return result[0].get("id")
    return None


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


async def _answer_with_candidates(query_text: str, collection: str, candidates: List[Dict[str, Any]], llm_client_override: Optional[LMStudioClient] = None) -> Dict[str, Any]:
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

    _client = llm_client_override or llm_client
    answer = await _client.chat(
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


@app.get("/documentation", response_class=HTMLResponse)
async def documentation_page(request: Request):
    """Serve the documentation page"""
    return templates.TemplateResponse("documentation.html", {"request": request})


def _count_disk_files(collection_name: str) -> int:
    """Count supported files physically present in the uploads folder for a collection."""
    supported = {".pdf", ".txt", ".docx", ".md"}
    coll_dir = UPLOADS_DIR / collection_name
    if not coll_dir.exists():
        return 0
    return sum(1 for f in coll_dir.iterdir() if f.is_file() and f.suffix.lower() in supported)


@app.get("/collections")
async def list_collections():
    """List all collections with metadata from database"""
    try:
        if not db_collection_manager:
            # Fallback to file-based system if database is not available
            collections_metadata = collection_manager.list_collections()
            qdrant_collections = await vector_store.list_collections()

            result = []
            seen = set()

            for meta in collections_metadata:
                coll_name = meta["sanitized_name"]
                result.append({
                    "name": coll_name,
                    "display_name": meta["name"],
                    "description": meta.get("description", ""),
                    "image": meta.get("image"),
                    "file_count": meta.get("file_count", 0),
                    "disk_file_count": _count_disk_files(coll_name),
                    "created_at": meta.get("created_at"),
                    "has_metadata": True
                })
                seen.add(coll_name)

            for qc in qdrant_collections:
                if qc not in seen:
                    result.append({
                        "name": qc,
                        "display_name": qc,
                        "description": "",
                        "image": None,
                        "file_count": 0,
                        "disk_file_count": _count_disk_files(qc),
                        "created_at": None,
                        "has_metadata": False
                    })

            return {"status": "success", "collections": result}

        # Use database-backed collection manager
        collections = await db_collection_manager.list_collections()

        # Format for frontend
        result = []
        for coll in collections:
            result.append({
                "name": coll["name"],
                "display_name": coll["display_name"],
                "description": coll.get("description", ""),
                "image": coll.get("image_url"),
                "file_count": coll.get("file_count", 0),
                "disk_file_count": _count_disk_files(coll["name"]),
                "created_at": coll.get("created_at"),
                "has_metadata": True
            })

        logger.info(f"Returning {len(result)} collections from database")
        return {"status": "success", "collections": result}
    except Exception as e:
        logger.error(f"Error listing collections: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing collections: {str(e)}")


@app.get("/collections/{collection_name}/stats")
async def get_collection_stats(collection_name: str):
    """Return record count (Supabase) and file count (disk) for a collection."""
    record_count = 0
    if supabase:
        try:
            docs = await supabase.select(
                "Documents",
                select="id",
                filters={
                    "collection": f"eq.{collection_name}",
                    "ingestion_status": "eq.complete",
                    "is_active": "eq.true",
                },
            )
            record_count = len(docs) if docs else 0
        except Exception:
            pass
    return {
        "collection": collection_name,
        "record_count": record_count,
        "disk_file_count": _count_disk_files(collection_name),
    }


@app.post("/collections")
async def create_collection_with_metadata(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    image: Optional[UploadFile] = File(None)
):
    """Create a new collection in database"""
    try:
        logger.info(f"Received POST /collections request")
        logger.info(f"Creating collection: name={name}, description={description}, has_image={image is not None}")
        
        if not db_collection_manager:
            logger.error("Database collection manager not available - Supabase not initialized")
            raise HTTPException(status_code=503, detail="Database collection manager not available. Please check Supabase configuration.")
        
        # Read image data if provided
        image_data = None
        image_filename = None
        if image:
            image_data = await image.read()
            image_filename = image.filename
            logger.info(f"Image uploaded: {image_filename}, size: {len(image_data)} bytes")
        
        # Create collection in database
        collection = await db_collection_manager.create_collection(
            name=name,
            description=description,
            image_data=image_data,
            image_filename=image_filename
        )
        
        # Create Qdrant collection
        vector_size = embedding_generator.dimension
        await vector_store.ensure_collection(collection["name"], vector_size)
        
        logger.info(f"Collection '{name}' created successfully with ID {collection['id']}")
        
        return {
            "status": "success",
            "collection": collection["name"],
            "metadata": collection,
            "message": f"Collection '{name}' created successfully"
        }
    except ValueError as e:
        logger.error(f"ValueError creating collection: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating collection: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creating collection: {str(e)}")


@app.post("/create_collection")
async def create_collection_simple(payload: Dict[str, Any]):
    """Create collection (legacy endpoint for backward compatibility)"""
    try:
        collection = payload.get("collection", "").strip()
        if not collection:
            raise HTTPException(status_code=400, detail="Collection name is required")
        
        # Create with basic metadata
        metadata = collection_manager.create_collection(name=collection)
        
        # Create Qdrant collection
        vector_size = embedding_generator.dimension
        await vector_store.ensure_collection(metadata["sanitized_name"], vector_size)
        
        return {"status": "success", "collection": metadata["sanitized_name"], "message": f"Collection '{collection}' created successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating collection: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating collection: {str(e)}")


@app.put("/collections/{collection_name}")
async def update_collection(
    collection_name: str,
    display_name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None)
):
    """Update collection metadata in database"""
    try:
        logger.info(f"Updating collection: {collection_name}")
        
        if not db_collection_manager:
            raise HTTPException(status_code=503, detail="Database collection manager not available")
        
        # Read image data if provided
        image_data = None
        image_filename = None
        if image:
            image_data = await image.read()
            image_filename = image.filename
            logger.info(f"New image uploaded: {image_filename}, size: {len(image_data)} bytes")
        
        # Update collection in database
        collection = await db_collection_manager.update_collection(
            name=collection_name,
            display_name=display_name,
            description=description,
            image_data=image_data,
            image_filename=image_filename
        )
        
        logger.info(f"Collection '{collection_name}' updated successfully")
        
        return {
            "status": "success",
            "old_name": collection_name,
            "new_name": collection["name"],
            "metadata": collection,
            "message": f"Collection updated successfully"
        }
    except ValueError as e:
        logger.error(f"ValueError updating collection: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating collection: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error updating collection: {str(e)}")


@app.get("/collections/{collection_name}/image")
async def get_collection_image(collection_name: str):
    """Serve collection cover image"""
    try:
        image_path = collection_manager.get_collection_image_path(collection_name)
        if not image_path or not image_path.exists():
            raise HTTPException(status_code=404, detail="Image not found")
        
        return FileResponse(image_path)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving collection image: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error serving image: {str(e)}")


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
        start_time = time.time()
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
        
        # Check if collection-aware mode is requested
        use_collection_aware = payload.get("collection_aware", False) or os.getenv("USE_COLLECTION_AWARE_CHAT", "false").lower() == "true"
        
        if use_collection_aware and supabase and collection_retriever:
            # Use collection-aware retrieval and response generation
            logger.info("Using collection-aware chat mode")
            
            # Stage 1: Classify query
            plan = await query_planner.classify_query(user_text, collection)
            logger.info(f"Query classified as: {plan.intent} (scope: {plan.scope})")

            # Stage 2: Multi-stage retrieval
            retrieval_start = time.time()
            evidence_pack = await collection_retriever.retrieve(
                query_text=user_text,
                plan=plan,
                collection=collection
            )
            retrieval_time_ms = int((time.time() - retrieval_start) * 1000)
            
            # Stage 3: Generate response via routed LLM client
            llm_start = time.time()
            selected_client, llm_tier = llm_router.select_client(
                plan_intent=plan.intent, nlp_complexity=0.0, user_override="auto"
            )
            result = await ResponseGenerator(selected_client).generate_response(evidence_pack)
            answer = result.get("answer", "")
            llm_time_ms = int((time.time() - llm_start) * 1000)

            # Store metadata for response
            response_metadata = {
                "query_intent": plan.intent,
                "query_scope": plan.scope,
                "documents_used": result.get("documents_used", 0),
                "chunks_used": result.get("chunks_used", 0),
                "response_type": result.get("response_type", "unknown"),
                "llm_tier": llm_tier,
            }
        else:
            # Use traditional chunk-based retrieval
            mode = payload.get("retrieval_mode") or payload.get("mode") or os.getenv("RETRIEVAL_MODE") or "hybrid"
            top_k = _safe_int(payload.get("top_k"), int(os.getenv("RETRIEVAL_TOP_K") or "12"))
            fts_limit = _safe_int(payload.get("fts_limit"), int(os.getenv("RETRIEVAL_FTS_LIMIT") or "30"))
            vec_limit = _safe_int(payload.get("vec_limit"), int(os.getenv("RETRIEVAL_VEC_LIMIT") or "30"))

            retrieval_start = time.time()
            candidates = await _retrieve_candidates(
                collection=collection,
                query_text=user_text,
                mode=str(mode),
                top_k=top_k,
                fts_limit=fts_limit,
                vec_limit=vec_limit,
            )
            retrieval_time_ms = int((time.time() - retrieval_start) * 1000)
            
            llm_start = time.time()
            rag_result = await _answer_with_candidates(user_text, collection=collection, candidates=candidates)
            answer = rag_result.get("answer", "")
            llm_time_ms = int((time.time() - llm_start) * 1000)
            
            response_metadata = None
        
        response_time_ms = int((time.time() - start_time) * 1000)

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
        
        # Track query run for analytics
        query_run_id = None
        if query_tracker:
            try:
                retrieval_mode_str = response_metadata.get("query_intent") if response_metadata else str(mode)
                chunks_count = response_metadata.get("chunks_used") if response_metadata else (len(candidates) if 'candidates' in locals() else 0)
                
                query_run_result = await query_tracker.create_query_run(
                    user_query=user_text,
                    collection=collection,
                    retrieval_mode=retrieval_mode_str,
                    llm_model=model or "unknown",
                    session_id=session_id,
                    response_time_ms=response_time_ms,
                    retrieval_time_ms=retrieval_time_ms,
                    llm_time_ms=llm_time_ms,
                    chunks_retrieved=chunks_count
                )
                if query_run_result.get("status") == "success":
                    query_run_id = query_run_result.get("query_run", {}).get("id")
            except Exception as e:
                logger.warning(f"Failed to track query run: {str(e)}")

        if not stream:
            response_data = {
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
            # Include query_run_id for evaluation tracking
            if query_run_id:
                response_data["query_run_id"] = query_run_id
            # Include collection-aware metadata if available
            if response_metadata:
                response_data["metadata"] = {
                    **response_metadata,
                    "retrieval_time_ms": retrieval_time_ms,
                    "llm_time_ms": llm_time_ms,
                    "total_time_ms": response_time_ms
                }
            return response_data

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


@app.post("/v1/chat/completions/collection-aware")
async def collection_aware_chat(payload: Dict[str, Any]):
    """
    Collection-aware chat endpoint that uses query planning and multi-stage retrieval.
    This endpoint classifies queries and retrieves evidence from across the collection.
    """
    try:
        if not supabase or not collection_retriever:
            raise HTTPException(
                status_code=503,
                detail="Collection-aware chat requires Supabase. Please configure Supabase connection."
            )
        
        start_time = time.time()
        model = payload.get("model")
        collection = _collection_from_model(model)

        messages = payload.get("messages") or []
        if not isinstance(messages, list) or not messages:
            raise HTTPException(status_code=400, detail="messages must be a non-empty list")

        # Extract user query
        user_text = None
        for m in reversed(messages):
            if isinstance(m, dict) and m.get("role") == "user":
                user_text = m.get("content")
                break
        if not user_text or not isinstance(user_text, str):
            raise HTTPException(status_code=400, detail="No user message content found")

        stream = bool(payload.get("stream", False))
        
        # Stage 1: Classify the query and create a plan
        logger.info(f"Classifying query: {user_text[:100]}...")
        plan = await query_planner.classify_query(user_text, collection)
        logger.info(f"Query classified as: {plan.intent} (scope: {plan.scope})")
        
        # Stage 2: Execute multi-stage retrieval
        retrieval_start = time.time()
        evidence_pack = await collection_retriever.retrieve(
            query_text=user_text,
            plan=plan,
            collection=collection
        )
        retrieval_time_ms = int((time.time() - retrieval_start) * 1000)
        logger.info(f"Retrieved evidence from {len(evidence_pack.candidate_documents)} documents, "
                   f"{len(evidence_pack.chunks)} chunks in {retrieval_time_ms}ms")
        
        # Stage 3: Generate response via routed LLM client
        llm_start = time.time()
        selected_client, llm_tier = llm_router.select_client(
            plan_intent=plan.intent, nlp_complexity=0.0, user_override="auto"
        )
        result = await ResponseGenerator(selected_client).generate_response(evidence_pack)
        answer = result.get("answer", "")
        llm_time_ms = int((time.time() - llm_start) * 1000)
        
        response_time_ms = int((time.time() - start_time) * 1000)

        # Persist chat messages
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
        
        # Track query run for analytics
        query_run_id = None
        if query_tracker:
            try:
                query_run_result = await query_tracker.create_query_run(
                    user_query=user_text,
                    collection=collection,
                    retrieval_mode=plan.intent,
                    llm_model=model or "unknown",
                    session_id=session_id,
                    response_time_ms=response_time_ms,
                    retrieval_time_ms=retrieval_time_ms,
                    llm_time_ms=llm_time_ms,
                    chunks_retrieved=len(evidence_pack.chunks)
                )
                if query_run_result.get("status") == "success":
                    query_run_id = query_run_result.get("query_run", {}).get("id")
            except Exception as e:
                logger.warning(f"Failed to track query run: {str(e)}")

        if not stream:
            response_data = {
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
                "metadata": {
                    "query_intent": plan.intent,
                    "query_scope": plan.scope,
                    "documents_searched": evidence_pack.total_documents_searched,
                    "documents_used": result.get("documents_used", 0),
                    "chunks_used": result.get("chunks_used", 0),
                    "response_type": result.get("response_type", "unknown"),
                    "retrieval_time_ms": retrieval_time_ms,
                    "llm_time_ms": llm_time_ms,
                    "total_time_ms": response_time_ms
                }
            }
            if query_run_id:
                response_data["query_run_id"] = query_run_id
            return response_data

        # Streaming response
        async def event_stream():
            init = {
                "id": response_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
            }
            yield f"data: {json.dumps(init)}\n\n"

            chunk = {
                "id": response_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{"index": 0, "delta": {"content": answer}, "finish_reason": None}],
            }
            yield f"data: {json.dumps(chunk)}\n\n"

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
        logger.error(f"Error in collection-aware chat: {str(e)}", exc_info=True)
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
        
        # Check if a document with this filename already exists (without PDF)
        existing_doc = None
        if document_manager and supabase:
            try:
                docs = await supabase.select(
                    "Documents",
                    select="*",
                    filters={
                        "collection": f"eq.{safe_collection}",
                        "title": f"eq.{file.filename}",
                        "pdf_attached": "eq.false"
                    }
                )
                if docs and len(docs) > 0:
                    existing_doc = docs[0]
                    logger.info(f"Found existing document without PDF: {existing_doc['id']}")
            except Exception as e:
                logger.warning(f"Could not check for existing documents: {e}")
        
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

            # If we found an existing document, update it instead of creating new
            document_id = None
            job_id = None
            
            if existing_doc and document_manager:
                logger.info(f"Attaching PDF to existing document {existing_doc['id']}")
                document_id = existing_doc['id']
                
                # Create ingestion job
                job_result = await document_manager.create_ingestion_job(
                    document_id=document_id,
                    collection=safe_collection,
                    doc_id=str(result.get("doc_id") or ""),
                    parser_used="pypdf",
                    chunking_method="recursive",
                    embedding_model=os.getenv("EMBEDDING_MODEL", "unknown")
                )
                if job_result.get("status") == "success":
                    job_id = job_result.get("job", {}).get("id")
                
                await document_manager.attach_pdf(
                    document_id=existing_doc['id'],
                    filename=file.filename,
                    file_path=str(file_path),
                    file_size=file_path.stat().st_size
                )
                
                # Update ingestion status and job
                await supabase.update(
                    "Documents",
                    patch={"ingestion_status": "processing"},
                    filters={"id": f"eq.{existing_doc['id']}"}
                )
                
                if job_id:
                    await document_manager.update_ingestion_job(
                        job_id=job_id,
                        status="processing"
                    )
                
                # Store chunks
                if isinstance(chunk_texts, list) and len(chunk_texts) > 0:
                    await _supabase_replace_chunks(
                        collection=safe_collection,
                        doc_id=str(result.get("doc_id") or ""),
                        chunk_texts=[c for c in chunk_texts if isinstance(c, str)],
                        title=existing_doc.get('title') or file.filename,
                        authors=existing_doc.get('author') or "",
                        notes=existing_doc.get('notes') or "",
                        tags=existing_doc.get('tags') or [],
                    )
                    
                    # Mark as complete
                    chunk_count = len(chunk_texts)
                    await supabase.update(
                        "Documents",
                        patch={
                            "ingestion_status": "complete",
                            "chunk_count": chunk_count
                        },
                        filters={"id": f"eq.{existing_doc['id']}"}
                    )
                    
                    # Update job as complete
                    if job_id:
                        await document_manager.update_ingestion_job(
                            job_id=job_id,
                            status="complete",
                            chunks_created=chunk_count
                        )
            else:
                # Create new document
                document_id = await _supabase_upsert_document(
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
                
                # Create ingestion job
                if document_id and document_manager:
                    job_result = await document_manager.create_ingestion_job(
                        document_id=document_id,
                        collection=safe_collection,
                        doc_id=str(result.get("doc_id") or ""),
                        parser_used="pypdf",
                        chunking_method="recursive",
                        embedding_model=os.getenv("EMBEDDING_MODEL", "unknown")
                    )
                    if job_result.get("status") == "success":
                        job_id = job_result.get("job", {}).get("id")
                        
                        # Update job to processing
                        await document_manager.update_ingestion_job(
                            job_id=job_id,
                            status="processing"
                        )

                if isinstance(chunk_texts, list) and len(chunk_texts) > 0:
                    await _supabase_replace_chunks(
                        collection=safe_collection,
                        doc_id=str(result.get("doc_id") or ""),
                        chunk_texts=[c for c in chunk_texts if isinstance(c, str)],
                        title=(result.get("filename") or file.filename),
                        authors="",
                        notes="",
                        tags=[],
                    )
                    
                    # Update status to complete after chunks are stored
                    chunk_count = len([c for c in chunk_texts if isinstance(c, str)])
                    await supabase.update(
                        "Documents",
                        patch={
                            "ingestion_status": "complete",
                            "chunk_count": chunk_count
                        },
                        filters={
                            "collection": f"eq.{safe_collection}",
                            "doc_id": f"eq.{result.get('doc_id')}"
                        }
                    )
                    
                    # Update job as complete
                    if job_id:
                        await document_manager.update_ingestion_job(
                            job_id=job_id,
                            status="complete",
                            chunks_created=chunk_count
                        )
        except Exception as e:
            logger.warning(f"Failed to upsert Supabase document/chunks: {str(e)}")
            # Mark job as failed if it exists
            if job_id and document_manager:
                try:
                    await document_manager.update_ingestion_job(
                        job_id=job_id,
                        status="failed",
                        error_message=str(e)
                    )
                except Exception as job_err:
                    logger.error(f"Failed to update job status: {job_err}")
        
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

                    if isinstance(chunk_texts, list) and len(chunk_texts) > 0:
                        await _supabase_replace_chunks(
                            collection=safe_collection,
                            doc_id=str(result.get("doc_id") or ""),
                            chunk_texts=[c for c in chunk_texts if isinstance(c, str)],
                            title=(result.get("filename") or file.filename),
                            authors="",
                            notes="",
                            tags=[],
                        )
                        
                        # Update status to complete after chunks are stored
                        if supabase:
                            await supabase.update(
                                "Documents",
                                patch={
                                    "ingestion_status": "complete",
                                    "chunk_count": len([c for c in chunk_texts if isinstance(c, str)])
                                },
                                filters={
                                    "collection": f"eq.{safe_collection}",
                                    "doc_id": f"eq.{result.get('doc_id')}"
                                }
                            )
                            _job_log(job_id, f"Updated ingestion status to complete with {len([c for c in chunk_texts if isinstance(c, str)])} chunks")
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
    top_k: int = Form(12),
    fts_limit: int = Form(30),
    vec_limit: int = Form(30),
    retrieve_only: bool = Form(False),
    profile_name: Optional[str] = Form(None),
    bm25_weight: Optional[float] = Form(None),
    pg_fts_weight: Optional[float] = Form(None),
    pg_vec_weight: Optional[float] = Form(None),
    use_reranker: Optional[bool] = Form(None),
    normalize_scores: Optional[bool] = Form(None),
    llm_mode: str = Form("auto"),
):
    """Query the RAG system with optional retrieval profile, custom weights, and LLM mode."""
    try:
        safe_collection = collection.strip()
        if not safe_collection:
            raise HTTPException(status_code=400, detail="Collection is required")

        # Normalize llm_mode
        llm_mode = llm_mode.strip().lower()
        if llm_mode not in ("auto", "fast", "large"):
            llm_mode = "auto"

        # Profile-based retrieval settings
        if profile_name:
            from src.retrieval_profiles import get_builtin_profile
            profile = get_builtin_profile(profile_name)
            if not profile:
                raise HTTPException(status_code=400, detail=f"Unknown profile: {profile_name}")
            mode = "hybrid"
            top_k = profile.top_k
            fts_limit = profile.fts_limit
            vec_limit = profile.vec_limit

        if bm25_weight is not None or pg_fts_weight is not None or pg_vec_weight is not None:
            mode = "custom"

        # --- NLP analysis + LLM routing (runs for every query path) ---
        nlp_analysis = nlp_analyzer.analyze(query)
        plan = await query_planner.classify_query(query, safe_collection)
        selected_client, llm_tier = llm_router.select_client(
            plan_intent=plan.intent,
            nlp_complexity=nlp_analysis.complexity_score,
            user_override=llm_mode,
        )
        logger.info(
            "Query routed: intent=%s nlp_type=%s complexity=%.3f mode=%s → tier=%s",
            plan.intent, nlp_analysis.question_type, nlp_analysis.complexity_score, llm_mode, llm_tier,
        )

        nlp_meta = {
            "llm_tier": llm_tier,
            "llm_mode_requested": llm_mode,
            "nlp_complexity": nlp_analysis.complexity_score,
            "nlp_question_type": nlp_analysis.question_type,
            "nlp_entities": nlp_analysis.entities,
        }

        # Check if collection-aware mode is enabled
        use_collection_aware = os.getenv("USE_COLLECTION_AWARE_CHAT", "false").lower() == "true"

        if use_collection_aware and supabase and collection_retriever:
            logger.info("Using collection-aware chat mode for /query endpoint")

            evidence_pack = await collection_retriever.retrieve(
                query_text=query,
                plan=plan,
                collection=safe_collection,
            )

            # Build a per-request generator with the routed client
            request_generator = ResponseGenerator(selected_client)
            result = await request_generator.generate_response(evidence_pack)

            return {
                "status": "success",
                "response": result.get("answer", ""),
                "answer": result.get("answer", ""),
                "sources": result.get("sources", []),
                "mode": "collection_aware",
                "profile": profile_name,
                "metadata": {
                    "query_intent": plan.intent,
                    "query_scope": plan.scope,
                    "documents_used": result.get("documents_used", 0),
                    "chunks_used": result.get("chunks_used", 0),
                    "response_type": result.get("response_type", "unknown"),
                    **nlp_meta,
                },
            }
        else:
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
                result = await _answer_with_candidates(
                    query,
                    collection=safe_collection,
                    candidates=candidates,
                    llm_client_override=selected_client,
                )
            except Exception as e:
                raise HTTPException(
                    status_code=502,
                    detail=(
                        "Retrieved candidates successfully, but failed to generate an answer. "
                        "Check LM Studio is running and LM_STUDIO_BASE_URL/LM_STUDIO_MODEL are correct. "
                        f"Error: {str(e)}"
                    ),
                )
            return {
                "status": "success",
                "response": result.get("answer", ""),
                "answer": result.get("answer", ""),
                "sources": result.get("sources", []),
                "mode": (mode or "hybrid"),
                "profile": profile_name,
                "metadata": nlp_meta,
            }

    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

@app.post("/reindex")
async def reindex_collection(collection: str = Form(...)):
    """Re-index all uploaded files for a collection into the vector store."""
    safe_collection = collection.strip()
    if not safe_collection:
        raise HTTPException(status_code=400, detail="Collection is required")

    collection_dir = UPLOADS_DIR / safe_collection
    if not collection_dir.exists():
        raise HTTPException(status_code=404, detail=f"No uploads directory for collection: {safe_collection}")

    files = list(collection_dir.glob("*.pdf")) + list(collection_dir.glob("*.txt")) + list(collection_dir.glob("*.md"))
    if not files:
        return {"status": "ok", "message": "No files found to reindex", "indexed": 0, "failed": 0}

    indexed, failed, errors = 0, 0, []
    for file_path in files:
        try:
            await rag_engine.add_document(str(file_path), collection=safe_collection)
            indexed += 1
            logger.info(f"Reindexed: {file_path.name}")
        except Exception as e:
            failed += 1
            errors.append(f"{file_path.name}: {str(e)}")
            logger.error(f"Failed to reindex {file_path.name}: {e}")

    return {
        "status": "ok",
        "collection": safe_collection,
        "files_found": len(files),
        "indexed": indexed,
        "failed": failed,
        "errors": errors,
    }


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

        allowed = {"title", "authors", "abstract", "notes", "tags", "doi", "year"}
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

@app.get("/retrieval/profiles")
async def list_retrieval_profiles():
    """List all available retrieval profiles"""
    try:
        result = await retrieval_api.list_profiles()
        return result
    except Exception as e:
        logger.error(f"Error listing retrieval profiles: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing retrieval profiles: {str(e)}")


@app.get("/retrieval/profiles/{profile_name}")
async def get_retrieval_profile(profile_name: str):
    """Get a specific retrieval profile"""
    try:
        result = await retrieval_api.get_profile(profile_name)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting retrieval profile: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting retrieval profile: {str(e)}")


@app.post("/retrieval/profiles")
async def create_retrieval_profile(payload: Dict[str, Any]):
    """Create a new custom retrieval profile"""
    try:
        result = await retrieval_api.create_profile(payload)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating retrieval profile: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating retrieval profile: {str(e)}")


@app.put("/retrieval/profiles/{profile_name}")
async def update_retrieval_profile(profile_name: str, payload: Dict[str, Any]):
    """Update an existing retrieval profile"""
    try:
        result = await retrieval_api.update_profile(profile_name, payload)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating retrieval profile: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating retrieval profile: {str(e)}")


@app.delete("/retrieval/profiles/{profile_name}")
async def delete_retrieval_profile(profile_name: str):
    """Delete a custom retrieval profile"""
    try:
        result = await retrieval_api.delete_profile(profile_name)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting retrieval profile: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting retrieval profile: {str(e)}")


@app.get("/retrieval/projects/{collection}/profile")
async def get_project_retrieval_profile(collection: str):
    """Get the retrieval profile for a specific project/collection"""
    try:
        result = await retrieval_api.get_project_profile(collection)
        return result
    except Exception as e:
        logger.error(f"Error getting project retrieval profile: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting project retrieval profile: {str(e)}")


@app.put("/retrieval/projects/{collection}/profile")
async def set_project_retrieval_profile(collection: str, payload: Dict[str, Any]):
    """Set the retrieval profile for a specific project/collection"""
    try:
        profile_name = payload.get("profile_name")
        if profile_name:
            result = await retrieval_api.set_project_profile(collection, profile_name)
        else:
            bm25_weight = payload.get("bm25_weight")
            fts_weight = payload.get("fts_weight")
            vec_weight = payload.get("vec_weight")
            use_reranker = payload.get("use_reranker", False)
            
            if bm25_weight is None or fts_weight is None or vec_weight is None:
                raise HTTPException(status_code=400, detail="Either profile_name or custom weights required")
            
            result = await retrieval_api.set_project_custom_weights(
                collection, bm25_weight, fts_weight, vec_weight, use_reranker
            )
        
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting project retrieval profile: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error setting project retrieval profile: {str(e)}")


@app.get("/retrieval/benchmarks")
async def list_benchmark_queries(collection: Optional[str] = None, query_type: Optional[str] = None):
    """List benchmark queries"""
    try:
        result = await retrieval_api.list_benchmark_queries(collection, query_type)
        return result
    except Exception as e:
        logger.error(f"Error listing benchmark queries: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing benchmark queries: {str(e)}")


@app.post("/retrieval/benchmarks")
async def create_benchmark_query(payload: Dict[str, Any]):
    """Create a new benchmark query"""
    try:
        result = await retrieval_api.create_benchmark_query(payload)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating benchmark query: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating benchmark query: {str(e)}")


@app.post("/retrieval/benchmarks/bulk")
async def bulk_create_benchmark_queries(payload: Dict[str, Any]):
    """Bulk create benchmark queries"""
    try:
        queries = payload.get("queries", [])
        result = await retrieval_api.bulk_create_benchmark_queries(queries)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error bulk creating benchmark queries: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error bulk creating benchmark queries: {str(e)}")


@app.post("/retrieval/labels")
async def create_relevance_label(payload: Dict[str, Any]):
    """Create a relevance label for annotation"""
    try:
        result = await retrieval_api.create_relevance_label(payload)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating relevance label: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating relevance label: {str(e)}")


@app.post("/retrieval/labels/bulk")
async def bulk_create_relevance_labels(payload: Dict[str, Any]):
    """Bulk create relevance labels"""
    try:
        labels = payload.get("labels", [])
        result = await retrieval_api.bulk_create_relevance_labels(labels)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error bulk creating relevance labels: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error bulk creating relevance labels: {str(e)}")


@app.get("/retrieval/labels/{query_id}")
async def get_labels_for_query(query_id: str):
    """Get all relevance labels for a specific query"""
    try:
        result = await retrieval_api.get_labels_for_query(query_id)
        return result
    except Exception as e:
        logger.error(f"Error getting labels for query: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting labels for query: {str(e)}")


@app.post("/retrieval/annotations/sessions")
async def create_annotation_session(payload: Dict[str, Any]):
    """Create a new annotation session"""
    try:
        collection = payload.get("collection")
        annotator = payload.get("annotator")
        
        if not collection or not annotator:
            raise HTTPException(status_code=400, detail="collection and annotator are required")
        
        result = await retrieval_api.create_annotation_session(collection, annotator)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating annotation session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating annotation session: {str(e)}")


@app.get("/retrieval/runs")
async def list_retrieval_runs(collection: Optional[str] = None):
    """List retrieval evaluation runs"""
    try:
        result = await retrieval_api.list_retrieval_runs(collection)
        return result
    except Exception as e:
        logger.error(f"Error listing retrieval runs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing retrieval runs: {str(e)}")


@app.get("/retrieval/runs/best")
async def get_best_retrieval_run(collection: str, metric: str = "ndcg_at_10"):
    """Get the best retrieval run for a collection"""
    try:
        result = await retrieval_api.get_best_run(collection, metric)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting best retrieval run: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting best retrieval run: {str(e)}")


@app.get("/retrieval/optimizations")
async def list_optimizations(collection: Optional[str] = None):
    """List optimization history"""
    try:
        result = await retrieval_api.list_optimizations(collection)
        return result
    except Exception as e:
        logger.error(f"Error listing optimizations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing optimizations: {str(e)}")


@app.get("/documentation/{doc_type}")
async def get_documentation(doc_type: str):
    """Serve documentation as HTML"""
    try:
        # Map doc types to files
        doc_files = {
            "retrieval-guide": BASE_DIR / "RETRIEVAL_LAYER_GUIDE.md",
            "implementation": BASE_DIR / "IMPLEMENTATION_SUMMARY.md",
        }
        
        if doc_type not in doc_files:
            raise HTTPException(status_code=404, detail="Documentation not found")
        
        doc_path = doc_files[doc_type]
        if not doc_path.exists():
            raise HTTPException(status_code=404, detail="Documentation file not found")
        
        # Read markdown file
        markdown_content = doc_path.read_text(encoding="utf-8")
        
        # Convert markdown to HTML (basic conversion)
        html_content = markdown_to_html(markdown_content)
        
        return HTMLResponse(content=html_content)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving documentation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error serving documentation: {str(e)}")


def markdown_to_html(markdown_text: str) -> str:
    """Convert markdown to HTML with basic formatting"""
    import re
    
    html = markdown_text
    
    # Headers
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^#### (.+)$', r'<h4>\1</h4>', html, flags=re.MULTILINE)
    
    # Code blocks
    html = re.sub(r'```(\w+)?\n(.*?)```', r'<pre><code>\2</code></pre>', html, flags=re.DOTALL)
    
    # Inline code
    html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)
    
    # Bold
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    
    # Italic
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
    
    # Links
    html = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2">\1</a>', html)
    
    # Unordered lists
    lines = html.split('\n')
    in_list = False
    result = []
    for line in lines:
        if re.match(r'^- ', line):
            if not in_list:
                result.append('<ul>')
                in_list = True
            result.append(f'<li>{line[2:]}</li>')
        else:
            if in_list:
                result.append('</ul>')
                in_list = False
            result.append(line)
    if in_list:
        result.append('</ul>')
    html = '\n'.join(result)
    
    # Paragraphs
    html = re.sub(r'\n\n', '</p><p>', html)
    html = f'<p>{html}</p>'
    
    # Clean up empty paragraphs
    html = re.sub(r'<p>\s*</p>', '', html)
    html = re.sub(r'<p>\s*<h', '<h', html)
    html = re.sub(r'</h(\d)>\s*</p>', r'</h\1>', html)
    html = re.sub(r'<p>\s*<ul>', '<ul>', html)
    html = re.sub(r'</ul>\s*</p>', '</ul>', html)
    html = re.sub(r'<p>\s*<pre>', '<pre>', html)
    html = re.sub(r'</pre>\s*</p>', '</pre>', html)
    
    return html


@app.on_event("startup")
async def check_qdrant_on_startup():
    qdrant_url = os.getenv("QDRANT_URL") or "http://localhost:6333"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{qdrant_url}/healthz")
        if resp.status_code == 200:
            logger.info(f"Qdrant is healthy at {qdrant_url}")
        else:
            logger.warning(f"Qdrant at {qdrant_url} returned HTTP {resp.status_code} — vector search may fail")
    except Exception as e:
        logger.warning(f"Qdrant not reachable at {qdrant_url}: {e} — vector search will fail until Qdrant is started")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    qdrant_url = os.getenv("QDRANT_URL") or "http://localhost:6333"
    qdrant_ok = False
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{qdrant_url}/healthz")
        qdrant_ok = r.status_code == 200
    except Exception:
        pass
    return {"status": "healthy", "message": "Local RAG system is running", "qdrant": "ok" if qdrant_ok else "unavailable"}


@app.get("/api/settings")
async def get_settings():
    """Return current provider settings (API keys masked)."""
    import dataclasses
    data = dataclasses.asdict(provider_settings)
    for key in ("chat_api_key", "embedding_api_key"):
        if data.get(key):
            data[key] = data[key][:8] + "..." if len(data[key]) > 8 else "***"
    return data


@app.post("/api/settings")
async def save_settings(payload: Dict[str, Any]):
    """Update provider settings and reinitialise clients."""
    global provider_settings
    import dataclasses

    current = dataclasses.asdict(provider_settings)
    for field in ProviderSettings.__dataclass_fields__:
        if field in payload:
            val = payload[field]
            # Don't overwrite stored keys with masked placeholders
            if isinstance(val, str) and val.endswith("..."):
                continue
            current[field] = val if val != "" else None

    provider_settings = ProviderSettings(**current)
    _save_settings_to_file(provider_settings)
    _apply_provider_settings(provider_settings)
    return {"status": "success", "message": "Settings saved and applied"}

# Chat Session Endpoints
@app.post("/chat/sessions")
async def create_chat_session(payload: Dict[str, Any]):
    """Create a new chat session"""
    if not chat_manager:
        raise HTTPException(status_code=503, detail="Chat history not available")
    
    try:
        title = payload.get("title", "New Chat")
        collection = payload.get("collection")
        
        result = await chat_manager.create_session(title, collection)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        
        return result
    except Exception as e:
        logger.error(f"Error creating chat session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating chat session: {str(e)}")


@app.get("/chat/sessions")
async def list_chat_sessions(collection: Optional[str] = None, limit: int = 50):
    """List chat sessions"""
    if not chat_manager:
        raise HTTPException(status_code=503, detail="Chat history not available")
    
    try:
        result = await chat_manager.list_sessions(collection, limit)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        
        return result
    except Exception as e:
        logger.error(f"Error listing chat sessions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing chat sessions: {str(e)}")


@app.get("/chat/sessions/{session_id}")
async def get_chat_session(session_id: str):
    """Get a specific chat session"""
    if not chat_manager:
        raise HTTPException(status_code=503, detail="Chat history not available")
    
    try:
        result = await chat_manager.get_session(session_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        
        return result
    except Exception as e:
        logger.error(f"Error getting chat session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting chat session: {str(e)}")


@app.put("/chat/sessions/{session_id}")
async def update_chat_session(session_id: str, payload: Dict[str, Any]):
    """Update a chat session"""
    if not chat_manager:
        raise HTTPException(status_code=503, detail="Chat history not available")
    
    try:
        title = payload.get("title")
        result = await chat_manager.update_session(session_id, title)
        
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        
        return result
    except Exception as e:
        logger.error(f"Error updating chat session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating chat session: {str(e)}")


@app.delete("/chat/sessions/{session_id}")
async def delete_chat_session(session_id: str):
    """Delete a chat session"""
    if not chat_manager:
        raise HTTPException(status_code=503, detail="Chat history not available")
    
    try:
        result = await chat_manager.delete_session(session_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        
        return result
    except Exception as e:
        logger.error(f"Error deleting chat session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting chat session: {str(e)}")


@app.get("/chat/sessions/{session_id}/messages")
async def get_chat_messages(session_id: str):
    """Get messages for a chat session"""
    if not chat_manager:
        raise HTTPException(status_code=503, detail="Chat history not available")
    
    try:
        result = await chat_manager.get_messages(session_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        
        return result
    except Exception as e:
        logger.error(f"Error getting chat messages: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting chat messages: {str(e)}")


@app.post("/chat/sessions/{session_id}/messages")
async def add_chat_message(session_id: str, payload: Dict[str, Any]):
    """Add a message to a chat session"""
    if not chat_manager:
        raise HTTPException(status_code=503, detail="Chat history not available")
    
    try:
        role = payload.get("role")
        content = payload.get("content")
        sources = payload.get("sources")
        retrieval_profile = payload.get("retrieval_profile")
        
        if not role or not content:
            raise HTTPException(status_code=400, detail="role and content are required")
        
        result = await chat_manager.add_message(session_id, role, content, sources, retrieval_profile)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        
        return result
    except Exception as e:
        logger.error(f"Error adding chat message: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error adding chat message: {str(e)}")


# ============================================================================
# DASHBOARD & DOCUMENT MANAGEMENT ENDPOINTS
# ============================================================================

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Render the dashboard page"""
    return templates.TemplateResponse("dashboard.html", {"request": request})


# Document Management Endpoints
@app.post("/api/documents")
async def create_document_api(payload: Dict[str, Any]):
    """Create a new document record"""
    if not document_manager:
        raise HTTPException(status_code=503, detail="Document management not available")

    try:
        result = await document_manager.create_document(**payload)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        if crossref_enricher and payload.get("doi"):
            doc_id = result.get("document", {}).get("id")
            if doc_id:
                asyncio.create_task(crossref_enricher.enrich_document(doc_id))
        return result
    except Exception as e:
        logger.error(f"Error creating document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/documents")
async def list_documents_api(
    collection: Optional[str] = None,
    project_id: Optional[str] = None,
    ingestion_status: Optional[str] = None,
    document_type: Optional[str] = None,
    limit: int = 100
):
    """List documents with filters"""
    if not document_manager:
        raise HTTPException(status_code=503, detail="Document management not available")
    
    try:
        result = await document_manager.list_documents(
            collection=collection,
            project_id=project_id,
            ingestion_status=ingestion_status,
            document_type=document_type,
            limit=limit
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/documents/{document_id}")
async def get_document_api(document_id: int):
    """Get a single document"""
    if not document_manager:
        raise HTTPException(status_code=503, detail="Document management not available")
    
    try:
        result = await document_manager.get_document(document_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except Exception as e:
        logger.error(f"Error getting document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/documents/{document_id}")
async def update_document_api(document_id: int, payload: Dict[str, Any]):
    """Update document metadata"""
    if not document_manager:
        raise HTTPException(status_code=503, detail="Document management not available")

    try:
        result = await document_manager.update_document(document_id, **payload)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        if crossref_enricher and payload.get("doi"):
            asyncio.create_task(crossref_enricher.enrich_document(document_id))
        return result
    except Exception as e:
        logger.error(f"Error updating document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/documents/{document_id}")
async def delete_document_api(document_id: int):
    """Delete a document"""
    if not document_manager:
        raise HTTPException(status_code=503, detail="Document management not available")
    
    try:
        result = await document_manager.delete_document(document_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/documents/add-manual")
async def add_document_manual_api(payload: Dict[str, Any]):
    """Add a document manually without PDF (workflow 2)"""
    if not document_manager:
        raise HTTPException(status_code=503, detail="Document management not available")
    
    try:
        collection = payload.get("collection")
        if not collection:
            raise HTTPException(status_code=400, detail="Collection is required")
        
        result = await document_manager.create_document(
            collection=collection,
            title=payload.get("title"),
            document_type=payload.get("document_type"),
            author=payload.get("author"),
            year=payload.get("year"),
            doi=payload.get("doi"),
            abstract=payload.get("abstract"),
            notes=payload.get("notes"),
            tags=payload.get("tags"),
            source_type="manual_entry",
            user_id=payload.get("user_id", "default_user")
        )

        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        if crossref_enricher and payload.get("doi"):
            doc_id = result.get("document", {}).get("id")
            if doc_id:
                asyncio.create_task(crossref_enricher.enrich_document(doc_id))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding document manually: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/documents/attach-pdf/{document_id}")
async def attach_pdf_to_document_api(document_id: int, file: UploadFile = File(...)):
    """Attach a PDF to an existing document record"""
    if not document_manager:
        raise HTTPException(status_code=503, detail="Document management not available")
    
    try:
        # Save the uploaded file
        file_content = await file.read()
        filename = file.filename or f"document_{document_id}.pdf"
        
        # Create uploads directory if it doesn't exist
        upload_path = UPLOADS_DIR / filename
        with open(upload_path, "wb") as f:
            f.write(file_content)
        
        # Attach PDF to document
        result = await document_manager.attach_pdf(
            document_id=document_id,
            file_path=str(upload_path),
            filename=filename,
            file_size=len(file_content)
        )
        
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))

        # Kick off ingestion immediately so the file doesn't sit queued forever
        doc = result.get("document", {})
        collection = doc.get("collection")
        if collection:
            asyncio.create_task(_ingest_pdf_for_doc(doc, upload_path, collection))

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error attaching PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/documents/process-queued/{collection}")
async def process_queued_documents_api(collection: str):
    """Kick off ingestion for every document that is queued but has a PDF attached."""
    if not document_manager or not supabase:
        raise HTTPException(status_code=503, detail="Services not available")
    try:
        rows = await supabase.select(
            "Documents",
            select="*",
            filters={
                "collection": f"eq.{collection}",
                "ingestion_status": "eq.queued",
                "pdf_attached": "eq.true",
                "is_active": "eq.true",
            },
            limit=500,
        )
        if not rows:
            return {"status": "nothing_to_process", "queued": 0}

        launched = 0
        skipped = 0
        for doc in rows:
            file_path = doc.get("file_path")
            if not file_path:
                skipped += 1
                continue
            asyncio.create_task(_ingest_pdf_for_doc(doc, Path(file_path), collection))
            launched += 1

        logger.info(f"process-queued '{collection}': launched {launched}, skipped {skipped} (no file_path)")
        return {"status": "processing", "queued": launched, "skipped": skipped}
    except Exception as e:
        logger.error(f"Error processing queued documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/documents/bulk-import")
async def bulk_import_documents_api(file: UploadFile = File(...), collection: str = Form(...)):
    """Bulk import documents from CSV file (workflow 3)"""
    if not document_manager:
        raise HTTPException(status_code=503, detail="Document management not available")
    
    try:
        import csv
        import io
        
        # Read CSV file
        content = await file.read()
        csv_text = content.decode('utf-8-sig')
        csv_reader = csv.DictReader(io.StringIO(csv_text))
        
        # Convert CSV rows to list of dicts
        documents = list(csv_reader)
        
        if not documents:
            raise HTTPException(status_code=400, detail="CSV file is empty")
        
        # Bulk import
        result = await document_manager.bulk_import_documents(
            documents=documents,
            collection=collection,
            user_id="default_user",
            source_type="csv_import"
        )
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing CSV: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



async def _enrich_ris_batch(doc_ids: List[int], collection: str) -> None:
    """Background task: run CrossRef enrichment for a batch of imported RIS records."""
    if not crossref_enricher:
        return
    counts: Dict[str, int] = {"enriched": 0, "skipped": 0, "not_found": 0, "errors": 0}
    logger.info(f"RIS CrossRef enrichment started: {len(doc_ids)} records in '{collection}'")
    for doc_id in doc_ids:
        try:
            result = await crossref_enricher.enrich_document(doc_id, overwrite=False)
            s = result.get("status", "error")
            counts[s if s in counts else "errors"] += 1
        except Exception as e:
            logger.warning(f"CrossRef enrichment failed for doc {doc_id}: {e}")
            counts["errors"] += 1
    logger.info(
        f"RIS CrossRef enrichment complete for '{collection}': "
        f"enriched={counts['enriched']} not_found={counts['not_found']} "
        f"skipped={counts['skipped']} errors={counts['errors']}"
    )


@app.post("/api/documents/import-ris")
async def import_ris_documents_api(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    collection: str = Form(...),
):
    """Import documents from a RIS bibliography file. Records are inserted immediately;
    CrossRef enrichment runs in the background after the response is returned."""
    if not document_manager:
        raise HTTPException(status_code=503, detail="Document management not available")

    try:
        from src.ris_parser import parse_ris

        content = await file.read()
        try:
            ris_text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            ris_text = content.decode("latin-1")

        documents = parse_ris(ris_text)
        if not documents:
            raise HTTPException(status_code=400, detail="No records found in RIS file")

        import_result = await document_manager.bulk_import_documents(
            documents=documents,
            collection=collection,
            user_id="default_user",
            source_type="ris_import",
        )

        # Schedule CrossRef enrichment as a background task so the response returns immediately
        doc_ids = [doc["id"] for doc in import_result.get("imported", []) if doc.get("id")]
        if doc_ids:
            background_tasks.add_task(_enrich_ris_batch, doc_ids, collection)

        return {
            **import_result,
            "crossref": "running_in_background",
            "crossref_queued": len(doc_ids),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing RIS: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ── PDF Finder: local scan ────────────────────────────────────────────────────

async def _ingest_pdf_for_doc(doc: Dict[str, Any], pdf_path: Path, collection: str) -> bool:
    """Full ingest pipeline for a single PDF matched to an existing document record."""
    import shutil
    document_id = doc.get("id")
    try:
        # 1. Copy PDF into the collection uploads directory (mirrors normal upload path)
        collection_dir = UPLOADS_DIR / collection
        collection_dir.mkdir(parents=True, exist_ok=True)
        dest = collection_dir / pdf_path.name
        if dest.resolve() != pdf_path.resolve() and not dest.exists():
            shutil.copy2(str(pdf_path), str(dest))
        elif dest.resolve() != pdf_path.resolve():
            dest = collection_dir / f"doc{document_id}_{pdf_path.name}"
            shutil.copy2(str(pdf_path), str(dest))

        # 2. Attach PDF to the document record
        await document_manager.attach_pdf(
            document_id=document_id,
            file_path=str(dest),
            filename=dest.name,
            file_size=dest.stat().st_size,
        )
        await supabase.update(
            "Documents",
            patch={"ingestion_status": "processing"},
            filters={"id": f"eq.{document_id}"},
        )

        # 3. Full ingest via rag_engine — generates embeddings and stores vectors in Qdrant
        try:
            result = await rag_engine.add_document(str(dest), collection=collection)
        except Exception as ve:
            logger.warning(f"Vector ingest failed for {dest.name}, falling back to text-only: {ve}")
            result = await _process_document_only(dest)

        processed = result.get("processed") or {}
        chunk_texts = processed.get("chunk_texts") or []
        new_doc_id = str(result.get("doc_id") or "")

        # 4. Update the document record's doc_id to the processor-generated one so Qdrant
        #    payload lookups resolve back to this record correctly
        if new_doc_id:
            await supabase.update(
                "Documents",
                patch={"doc_id": new_doc_id},
                filters={"id": f"eq.{document_id}"},
            )

        # 5. Store text chunks in Supabase for hybrid / FTS search
        if chunk_texts and new_doc_id:
            await _supabase_replace_chunks(
                collection=collection,
                doc_id=new_doc_id,
                chunk_texts=[c for c in chunk_texts if isinstance(c, str)],
                title=doc.get("title") or dest.name,
                authors=doc.get("author") or "",
                notes=doc.get("notes") or "",
                tags=doc.get("tags") or [],
            )

        # 6. Mark complete
        await supabase.update(
            "Documents",
            patch={"ingestion_status": "complete", "chunk_count": len(chunk_texts)},
            filters={"id": f"eq.{document_id}"},
        )
        logger.info(f"Ingested '{dest.name}' for doc {document_id} ({len(chunk_texts)} chunks)")
        return True
    except Exception as e:
        logger.error(f"Ingest failed for doc {document_id} ({pdf_path.name}): {e}")
        await supabase.update(
            "Documents",
            patch={"ingestion_status": "failed", "processing_error": str(e)[:500]},
            filters={"id": f"eq.{document_id}"},
        )
        return False


async def _scan_local_pdfs_task(collection: str, docs: List[Dict[str, Any]], scan_dir: Path) -> None:
    from src.pdf_scanner import find_pdf_matches
    logger.info(f"Local PDF scan started for '{collection}': {len(docs)} unattached docs, scanning {scan_dir}")
    matches = find_pdf_matches(docs, scan_dir)
    # Build a lookup from document_id → full doc record
    doc_map = {d["id"]: d for d in docs}
    ingested = 0
    for m in matches:
        doc = doc_map.get(m["document_id"])
        if not doc:
            continue
        ok = await _ingest_pdf_for_doc(doc, Path(m["pdf_path"]), collection)
        if ok:
            ingested += 1
            logger.info(f"  Ingested '{m['pdf_name']}' → '{m['document_title'][:60]}' ({m['score']:.2f})")
    logger.info(f"Local PDF scan complete for '{collection}': {ingested}/{len(matches)} ingested")


@app.get("/api/documents/ingest-status/{collection}")
async def ingest_status_api(collection: str):
    """Return ingestion status counts for all documents in a collection."""
    if not supabase:
        raise HTTPException(status_code=503, detail="Database not available")
    try:
        rows = await supabase.select(
            "Documents",
            select="ingestion_status",
            filters={"collection": f"eq.{collection}", "is_active": "eq.true"},
            limit=2000,
        )
        counts: Dict[str, int] = {}
        for r in (rows or []):
            s = r.get("ingestion_status") or "unknown"
            counts[s] = counts.get(s, 0) + 1
        return {"collection": collection, "counts": counts, "total": len(rows or [])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/documents/find-pdfs/local")
async def find_pdfs_local_api(background_tasks: BackgroundTasks, collection: str = Form(...)):
    """Scan the Herb files directory for PDFs matching unattached records in a collection."""
    if not document_manager:
        raise HTTPException(status_code=503, detail="Document management not available")
    if not HERB_FILES_DIR.exists():
        raise HTTPException(status_code=404, detail=f"Herb files directory not found: {HERB_FILES_DIR}")
    try:
        rows = await supabase.select(
            "Documents",
            select="id,doc_id,title,author,year,notes,tags",
            filters={"collection": f"eq.{collection}", "pdf_attached": "eq.false", "is_active": "eq.true"},
            limit=500,
        )
        if not rows:
            return {"status": "nothing_to_match", "unattached_count": 0}
        background_tasks.add_task(_scan_local_pdfs_task, collection, rows, HERB_FILES_DIR)
        return {"status": "scanning", "unattached_count": len(rows), "scan_dir": str(HERB_FILES_DIR)}
    except Exception as e:
        logger.error(f"Local PDF scan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── PDF Finder: open access (Unpaywall) ──────────────────────────────────────

async def _fetch_open_access_task(docs: List[Dict[str, Any]], collection: str, mailto: str) -> None:
    from src.open_access_finder import fetch_unpaywall, download_pdf, safe_filename
    import asyncio
    counts: Dict[str, int] = {"found": 0, "ingested": 0, "not_found": 0, "errors": 0}
    logger.info(f"Open-access fetch started for '{collection}': {len(docs)} docs with DOIs")
    for doc in docs:
        doi = (doc.get("doi") or "").strip()
        if not doi:
            continue
        await asyncio.sleep(1.0)  # respect Unpaywall rate limits
        try:
            pdf_url = await fetch_unpaywall(doi, mailto)
            if not pdf_url:
                counts["not_found"] += 1
                continue
            counts["found"] += 1
            filename = safe_filename(doc.get("title") or f"doc_{doc['id']}", doc["id"])
            dest = UPLOADS_DIR / filename
            ok = await download_pdf(pdf_url, dest)
            if ok:
                success = await _ingest_pdf_for_doc(doc, dest, collection)
                if success:
                    counts["ingested"] += 1
                else:
                    counts["errors"] += 1
            else:
                counts["errors"] += 1
        except Exception as e:
            logger.warning(f"OA fetch failed for DOI {doi!r}: {e}")
            counts["errors"] += 1
    logger.info(
        f"Open-access fetch complete for '{collection}': "
        f"found={counts['found']} ingested={counts['ingested']} "
        f"not_found={counts['not_found']} errors={counts['errors']}"
    )


@app.post("/api/documents/find-pdfs/open-access")
async def find_pdfs_open_access_api(background_tasks: BackgroundTasks, collection: str = Form(...)):
    """Query Unpaywall for open-access PDFs for all unattached records that have a DOI."""
    if not document_manager:
        raise HTTPException(status_code=503, detail="Document management not available")
    if not supabase:
        raise HTTPException(status_code=503, detail="Database not available")
    mailto = os.getenv("CROSSREF_MAILTO", "")
    if not mailto:
        raise HTTPException(status_code=503, detail="CROSSREF_MAILTO not set in .env — required for Unpaywall")
    try:
        rows = await supabase.select(
            "Documents",
            select="id,doc_id,title,author,doi,notes,tags",
            filters={
                "collection": f"eq.{collection}",
                "pdf_attached": "eq.false",
                "is_active": "eq.true",
                "doi": "not.is.null",
            },
            limit=500,
        )
        if not rows:
            return {"status": "nothing_to_fetch", "queued": 0}
        background_tasks.add_task(_fetch_open_access_task, rows, collection, mailto)
        return {"status": "fetching", "queued": len(rows)}
    except Exception as e:
        logger.error(f"Open-access fetch error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Ingestion Job Endpoints
@app.get("/api/ingestion/jobs")
async def list_ingestion_jobs_api(
    status: Optional[str] = None,
    collection: Optional[str] = None,
    limit: int = 50
):
    """List ingestion jobs"""
    if not document_manager:
        raise HTTPException(status_code=503, detail="Document management not available")
    
    try:
        result = await document_manager.list_jobs_by_status(status, collection, limit)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except Exception as e:
        logger.error(f"Error listing jobs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# CrossRef Enrichment Endpoints

@app.get("/api/documents/{document_id}/crossref-preview")
async def crossref_preview_api(document_id: int):
    """Preview CrossRef lookup result for a document without writing anything."""
    if not crossref_enricher:
        raise HTTPException(status_code=503, detail="CrossRef enrichment not available")
    try:
        return await crossref_enricher.preview_document(document_id)
    except Exception as e:
        logger.error(f"CrossRef preview error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/documents/{document_id}/enrich")
async def enrich_document_api(document_id: int, overwrite: bool = False):
    """Enrich a single document with CrossRef metadata."""
    if not crossref_enricher:
        raise HTTPException(status_code=503, detail="CrossRef enrichment not available")
    try:
        result = await crossref_enricher.enrich_document(document_id, overwrite=overwrite)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CrossRef enrich error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/documents/enrich-batch")
async def enrich_batch_api(collection: Optional[str] = None, overwrite: bool = False, limit: int = 200):
    """Batch-enrich all metadata-incomplete documents in a collection."""
    if not crossref_enricher:
        raise HTTPException(status_code=503, detail="CrossRef enrichment not available")
    try:
        result = await crossref_enricher.enrich_collection(
            collection=collection, overwrite=overwrite, limit=limit
        )
        return result
    except Exception as e:
        logger.error(f"CrossRef batch enrich error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Query Run Endpoints
@app.post("/api/query-runs")
async def create_query_run_api(payload: Dict[str, Any]):
    """Create a query run record"""
    if not query_tracker:
        raise HTTPException(status_code=503, detail="Query tracking not available")
    
    try:
        result = await query_tracker.create_query_run(**payload)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except Exception as e:
        logger.error(f"Error creating query run: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/query-runs")
async def list_query_runs_api(
    collection: Optional[str] = None,
    session_id: Optional[str] = None,
    use_case_type: Optional[str] = None,
    limit: int = 50
):
    """List query runs"""
    if not query_tracker:
        raise HTTPException(status_code=503, detail="Query tracking not available")
    
    try:
        result = await query_tracker.list_query_runs(
            collection=collection,
            session_id=session_id,
            use_case_type=use_case_type,
            limit=limit
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except Exception as e:
        logger.error(f"Error listing query runs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/query-runs/{query_run_id}")
async def get_query_run_api(query_run_id: str):
    """Get a query run"""
    if not query_tracker:
        raise HTTPException(status_code=503, detail="Query tracking not available")
    
    try:
        result = await query_tracker.get_query_run(query_run_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except Exception as e:
        logger.error(f"Error getting query run: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Evaluation Endpoints
@app.post("/api/evaluations")
async def create_evaluation_api(payload: Dict[str, Any]):
    """Create an evaluation"""
    if not evaluation_manager:
        raise HTTPException(status_code=503, detail="Evaluation not available")
    
    try:
        result = await evaluation_manager.create_evaluation(**payload)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except Exception as e:
        logger.error(f"Error creating evaluation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/evaluations/{evaluation_id}")
async def get_evaluation_api(evaluation_id: str):
    """Get an evaluation"""
    if not evaluation_manager:
        raise HTTPException(status_code=503, detail="Evaluation not available")
    
    try:
        result = await evaluation_manager.get_evaluation(evaluation_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except Exception as e:
        logger.error(f"Error getting evaluation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Analytics Endpoints
@app.get("/api/analytics/documents")
async def get_document_analytics_api(
    collection: Optional[str] = None,
    limit: int = 100
):
    """Get document analytics"""
    if not analytics_manager:
        raise HTTPException(status_code=503, detail="Analytics not available")
    
    try:
        result = await analytics_manager.get_document_analytics(collection=collection, limit=limit)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except Exception as e:
        logger.error(f"Error getting document analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analytics/retrieval-modes")
async def get_retrieval_mode_analytics_api(
    collection: Optional[str] = None,
    use_case_type: Optional[str] = None
):
    """Get retrieval mode analytics"""
    if not analytics_manager:
        raise HTTPException(status_code=503, detail="Analytics not available")
    
    try:
        result = await analytics_manager.get_retrieval_mode_analytics(
            collection=collection,
            use_case_type=use_case_type
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except Exception as e:
        logger.error(f"Error getting retrieval mode analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analytics/models")
async def get_model_comparison_api(collection: Optional[str] = None):
    """Get model comparison analytics"""
    if not analytics_manager:
        raise HTTPException(status_code=503, detail="Analytics not available")
    
    try:
        result = await analytics_manager.get_model_comparison(collection=collection)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except Exception as e:
        logger.error(f"Error getting model comparison: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analytics/dashboard")
async def get_dashboard_summary_api(collection: Optional[str] = None):
    """Get dashboard summary"""
    if not analytics_manager:
        raise HTTPException(status_code=503, detail="Analytics not available")
    
    try:
        result = await analytics_manager.get_dashboard_summary(collection=collection)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except Exception as e:
        logger.error(f"Error getting dashboard summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Catch-all route for chat conversations - MUST be last to avoid conflicts with API routes
@app.get("/chat/{conversation_id}", response_class=HTMLResponse)
async def chat_conversation(request: Request, conversation_id: str):
    """Serve the main web interface with a specific conversation loaded"""
    return templates.TemplateResponse("index.html", {"request": request, "conversation_id": conversation_id})


if __name__ == "__main__":
    reload_enabled = (os.getenv("UVICORN_RELOAD") or "").strip() == "1"
    uvicorn.run("main:app", host="0.0.0.0", port=8010, reload=reload_enabled)
