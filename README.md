# Herb AI Local RAG System

A locally hosted RAG system with hybrid retrieval (lexical + semantic search):

- **Vector DB**: Qdrant (semantic search)
- **Relational DB**: Supabase Postgres (full-text search + metadata)
- **LLM & Embeddings**: Ollama (`qwen2.5:7b` + `mxbai-embed-large`)
- **Retrieval**: Hybrid search combining FTS (BM25-like) and vector search via Reciprocal Rank Fusion (RRF)
- **UI**: Simple chat UI with file upload

This project exposes an **OpenAI-compatible API** at `/v1/chat/completions`.

## Prerequisites

1. **Docker Desktop** installed and running
2. **Supabase self-hosted stack** running (see Supabase setup below)
3. **Drop folder** for PDFs: `C:\HerbData\Herb_files` (configurable via `DROP_FOLDER_PATH`)

## Quick Start

1. **Start Supabase** (one-time setup, see below)
2. **Run the RAG stack**:

```bash
cd "c:\Herb Project\LM-Open-Rag"
docker compose up -d
```

This starts:
- `qdrant` on `http://localhost:6333`
- `ollama` on `http://localhost:11434`
- `rag-api` on `http://localhost:8010`

3. **Pull Ollama models** (one-time):

```bash
docker exec lm-open-rag-ollama-1 ollama pull mxbai-embed-large
docker exec lm-open-rag-ollama-1 ollama pull qwen2.5:7b
```

4. **Open the UI**: `http://localhost:8010`

## Supabase Setup

This project requires a **self-hosted Supabase** instance for metadata and full-text search.

1. **Clone Supabase self-hosted** (if not already done):

```bash
cd "c:\Herb Project"
git clone https://github.com/supabase/supabase
cd supabase\docker
```

2. **Generate secrets and start**:

```bash
cp .env.example .env
# Edit .env and set strong passwords
docker compose up -d
```

3. **Access Supabase Studio**: `http://localhost:8000` (default credentials in `.env`)

4. **Run SQL migration** (in Supabase Studio SQL Editor):

See `SUPABASE_MIGRATION.sql` in this repo for the full migration script. Key tables:
- `Documents`: Document metadata (filename, title, authors, tags, notes)
- `DocumentChunks`: Chunk text with `tsvector` for full-text search
- `fts_search()`: RPC function for BM25-like lexical retrieval

5. **Configure RAG API** with Supabase credentials:

Create `.env` in `LM-Open-Rag/`:

```bash
SUPABASE_URL=http://host.docker.internal:8000
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key-from-supabase-env
SUPABASE_ANON_KEY=your-anon-key-from-supabase-env
DROP_FOLDER_PATH=/herb_files
```

## API Usage

### Upload a document

```bash
curl -X POST "http://localhost:8010/upload" \
  -F "collection=test" \
  -F "file=@/path/to/document.pdf"
```

### Query with hybrid retrieval

```bash
# Full query with LLM answer
curl -X POST "http://localhost:8010/query" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data "collection=test&query=your+question&mode=hybrid&top_k=5"

# Retrieve-only (no LLM, just see candidates)
curl -X POST "http://localhost:8010/query" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data "collection=test&query=your+question&mode=fts&retrieve_only=true"
```

### OpenAI-compatible chat endpoint

```bash
curl -X POST "http://localhost:8010/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "rag-test",
    "messages": [{"role": "user", "content": "What is the reciprocal effects model?"}]
  }'
```

## Environment Variables

Create `.env` in the project root (not committed to git):

```bash
# Supabase connection (required)
SUPABASE_URL=http://host.docker.internal:8000
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_ANON_KEY=your-anon-key

# Drop folder (mounted into rag-api container)
DROP_FOLDER_PATH=/herb_files

# Ollama (defaults work with docker-compose setup)
LM_STUDIO_BASE_URL=http://ollama:11434/v1
LM_STUDIO_EMBEDDING_MODEL=mxbai-embed-large
LM_STUDIO_MODEL=qwen2.5:7b
LM_STUDIO_TIMEOUT_SECONDS=300
LM_STUDIO_EMBEDDING_BATCH_SIZE=16

# Qdrant (defaults work with docker-compose setup)
QDRANT_URL=http://qdrant:6333
```

## Architecture

### Hybrid Retrieval Pipeline

1. **Ingestion**:
   - PDF → text extraction + chunking
   - Chunks → Ollama embeddings → Qdrant (semantic search)
   - Chunks + metadata → Supabase `DocumentChunks` (full-text search)

2. **Retrieval** (3 modes):
   - `fts`: Postgres full-text search (BM25-like ranking)
   - `vector`: Qdrant semantic search
   - `hybrid`: RRF merge of FTS + vector results (default)

3. **Answer Generation**:
   - Top-K candidates → context
   - Ollama `qwen2.5:7b` → LLM answer

### Data Storage

- **Qdrant**: Vector embeddings (semantic search)
- **Supabase `Documents`**: Document metadata (filename, file_path, title, authors, tags, notes)
- **Supabase `DocumentChunks`**: Chunk text + `tsvector` for FTS
- **Local filesystem**: Uploaded PDFs in `data/uploads/<collection>/`

## Notes

- Each collection is a separate namespace (e.g., `test`, `research`)
- Deduplication: re-uploading the same file (by `doc_id` hash) replaces existing chunks
- Drop folder: `C:\HerbData\Herb_files` is mounted into the `rag-api` container as `/herb_files`
- Supabase runs on port 8000, RAG API on port 8010 to avoid conflicts

## Roadmap

- [x] Hybrid retrieval (FTS + vector + RRF)
- [x] Ollama integration
- [x] Supabase metadata persistence
- [ ] Cross-encoder reranker
- [ ] Metadata enrichment (extract authors/title from PDFs)
- [ ] UI improvements (metadata editing, retrieval mode toggles)
- [ ] Drop folder watcher (auto-ingest)
