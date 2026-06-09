# HerbGPT — Project Map for Claude Code

## Project Location
- **Root:** `C:\Herb Project\LM-Open-Rag\`
- **Data store:** `C:\Herb Project\HerbData\` and `C:\Herb Project\Herb_files\`
- **Runs at:** `http://localhost:8010/`

## What This Is
HerbGPT is a local, agentic RAG (Retrieval-Augmented Generation) system. It ingests PDFs and documents into collections, embeds them via a vector store (Supabase/pgvector), and answers queries using a local or cloud LLM. It has a web UI, a REST API, and a dashboard.

---

## Entry Point
| File | Role |
|------|------|
| `main.py` | FastAPI app entry point — starts the server, mounts routes |

---

## Backend Source — `src/`
| Module | Role |
|--------|------|
| `rag_engine.py` | Core RAG orchestration — ties retrieval + generation together |
| `retrieval_api.py` | REST API routes for retrieval |
| `hybrid_retrieval.py` | Combines vector + full-text search |
| `collection_retriever.py` | Retrieval scoped to a specific collection |
| `query_planner.py` | Agentic query planning layer |
| `query_tracker.py` | Tracks query history / analytics |
| `embeddings.py` | Embedding model interface |
| `vector_store.py` | Supabase pgvector store interface |
| `supabase_rest.py` | Low-level Supabase REST client |
| `document_processor.py` | PDF/text ingestion and chunking |
| `document_manager.py` | Document CRUD and status management |
| `collection_manager.py` | Collection CRUD (file-based) |
| `db_collection_manager.py` | Collection CRUD (database-backed) |
| `chat_manager.py` | Chat session and history management |
| `response_generator.py` | LLM response generation |
| `lm_studio_client.py` | LM Studio (local LLM) client |
| `gemini_client.py` | Google Gemini API client |
| `provider_config.py` | LLM provider switching config |
| `analytics_manager.py` | Usage analytics |
| `benchmark_manager.py` | RAG benchmark/evaluation runs |
| `evaluation_manager.py` | Document evaluation logic |
| `retrieval_evaluation.py` | Retrieval quality scoring |
| `retrieval_optimization.py` | Retrieval parameter tuning |
| `retrieval_profile_manager.py` | Saved retrieval profiles |
| `retrieval_profiles.py` | Profile definitions |
| `__init__.py` | Package init |

---

## Frontend — `static/` + `templates/`
| File | Role |
|------|------|
| `templates/index.html` | Main chat UI |
| `templates/dashboard.html` | Analytics/admin dashboard |
| `templates/documentation.html` | In-app docs |
| `static/app.js` | Chat UI logic |
| `static/dashboard.js` | Dashboard JS |
| `static/document-manager.js` | Document upload/manage UI |
| `static/styles.css` | Main stylesheet |
| `static/dashboard.css` | Dashboard styles |
| `static/chat-history.css` | Chat history styles |

---

## Data — `data/`
```
data/
  collections/          # Collection metadata
    herb_calibration/
    retrieval-augmented_generation__rag/
    test/
  uploads/              # Uploaded source documents per collection
    herb_calibration/
    retrieval-augmented_generation__rag/
    test/
  collection_images/    # Collection cover images
```

---

## Infrastructure & Config
| File | Role |
|------|------|
| `docker-compose.yml` / `Dockerfile` | Container deployment |
| `ecosystem.config.js` | PM2 process manager config |
| `.env` | Environment variables (secrets — never commit) |
| `.env.example` | Template for env setup |
| `requirements.txt` | Python dependencies |

---

## Database — Supabase (PostgreSQL + pgvector)
Key SQL migration files at project root:
- `SUPABASE_MIGRATION.sql` — baseline schema
- `RETRIEVAL_SCHEMA.sql` — vector/retrieval tables
- `CREATE_COLLECTIONS_TABLE.sql` — collections table
- `COMPLETE_MIGRATION.sql` — full migration bundle
- `MIGRATE_CHAT_HISTORY.sql` — chat history schema
- `DOCUMENT_EVALUATION_MIGRATION.sql` — evaluation tables

---

## PowerShell Helper Scripts
| Script | Role |
|--------|------|
| `restart_server.ps1` | Restart the FastAPI server |
| `start_with_ollama.ps1` | Start server with Ollama LLM backend |
| `setup_herbgpt_service.ps1` | Install as Windows service |
| `install_service.ps1` / `install_task_scheduler.ps1` | Alternative service install |
| `pull_model.ps1` / `update_model.ps1` | Ollama model management |
| `create_scheduled_task.ps1` | Windows Task Scheduler setup |
| `setup_pm2.ps1` | PM2 setup |

---

## Utility Scripts (Python)
| Script | Role |
|--------|------|
| `check_model_status.py` | Verify LLM model availability |
| `configure_ollama.py` | Switch to Ollama backend |
| `switch_to_lm_studio.py` | Switch to LM Studio backend |
| `switch_to_14b.py` | Switch to 14B model variant |
| `clean_herb_calibration.py` | Clean calibration data |
| `verify_cleanup.py` | Verify data cleanup |
| `run_migration.py` | Run DB migrations programmatically |
| `test_supabase.py` | Supabase connectivity test |
| `test_collection_aware.py` / `test_collection_aware_query.py` | Collection retrieval tests |
| `enable_collection_aware.py` | Enable collection-aware mode |

---

## LLM Backend Options
The system supports switching between:
1. **LM Studio** (local, via `lm_studio_client.py`)
2. **Ollama** (local, via `configure_ollama.py`)
3. **Google Gemini** (cloud, via `gemini_client.py`)

Active backend is controlled by `provider_config.py` and `.env`.

---

## Key Architectural Patterns
- **RAG pipeline:** ingest → chunk → embed → store in Supabase pgvector → query → hybrid retrieve (vector + FTS) → generate
- **Collections:** documents are organized into named collections; retrieval can be scoped to one or all collections
- **Agentic layer:** `query_planner.py` plans multi-step retrieval before generation
- **Chat history:** persisted in Supabase, managed by `chat_manager.py`

---

## Working Conventions
- Python backend (FastAPI), plain JS frontend (no framework)
- Supabase for vector store and relational data
- All secrets in `.env` — never hardcode or commit
- PowerShell is the local shell (Windows 11)
- Server runs on port **8010**
