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
from typing import Any, Dict, List, Optional
import logging
import time
import uuid


# Import our RAG modules
from src.rag_engine import RAGEngine
from src.document_processor import DocumentProcessor
from src.vector_store import VectorStore
from src.embeddings import EmbeddingGenerator
from src.lm_studio_client import LMStudioClient

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
        rag_result = await rag_engine.query(user_text, collection=collection)
        answer = rag_result.get("answer", "")

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
        
        # Process document and add to vector store
        result = await rag_engine.add_document(str(file_path), collection=safe_collection)
        
        return {
            "status": "success",
            "message": f"Document {file.filename} uploaded and processed successfully",
            "result": result,
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

                result = await rag_engine.add_document(
                    str(file_path),
                    collection=safe_collection,
                    progress_cb=lambda stage, current, total, msg=None: _job_progress(job_id, stage, current, total, msg),
                    log_cb=lambda msg: _job_log(job_id, msg),
                )
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
async def query_documents(collection: str = Form(...), query: str = Form(...)):
    """Query the RAG system"""
    try:
        safe_collection = collection.strip()
        if not safe_collection:
            raise HTTPException(status_code=400, detail="Collection is required")

        response = await rag_engine.query(query, collection=safe_collection)
        return {"status": "success", "response": response}
    
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
        return {"status": "success", "message": f"Document {doc_id} deleted successfully"}
    
    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting document: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "Local RAG system is running"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
