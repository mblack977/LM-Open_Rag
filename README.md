# Local RAG (Qdrant + LM Studio)

This is a locally hosted RAG system:

- Vector DB: **Qdrant** (runs in Docker Compose)
- LLM: **LM Studio** (OpenAI-compatible API, default `http://localhost:1234/v1`)
- UI: simple chat UI inspired by Open WebUI + file upload

This project also exposes an **OpenAI-compatible API** so you can use **Open WebUI** as the interface.

## Setup

1. Create and activate a virtual environment (recommended)
2. Install deps:

```bash
pip install -r requirements.txt
```

## Run

Start Qdrant (recommended via Docker Compose).

Start LM Studio server:

- Enable the **OpenAI compatible** server in LM Studio
- Ensure it is reachable at `http://localhost:1234/v1`

Run the app:

```bash
python main.py
```

Open:

- `http://localhost:8000`

## Use with Open WebUI (Option 1: model-per-collection)

This server exposes:

- `GET /v1/models`
- `POST /v1/chat/completions`

Each Qdrant collection is published as a “model” named:

- `rag-<collection>` (example: `rag-MTSS`)

In Open WebUI, configure the OpenAI API base URL to point to this server’s `/v1`.

Example (running on your host):

- Base URL: `http://localhost:8000/v1`

Then select the model `rag-MTSS` (or whichever collection you want) inside Open WebUI.

Note: Open WebUI doesn’t upload documents into Qdrant for you here; keep using this app’s `/upload` endpoint (or the built-in web page at `/`) to upload+index files per collection.

## Run with Docker Desktop

This repo includes a `Dockerfile` and `docker-compose.yml`.

`docker compose` will run:

- `rag-api` on `http://localhost:8000`
- `open-webui` on `http://localhost:3000`

This setup runs Qdrant in Docker Compose and expects LM Studio to run on the host.

On Windows/macOS, the `rag-api` container calls LM Studio via `host.docker.internal`.

Run:

```bash
docker compose up --build
```

Then:

- Open WebUI: `http://localhost:3000`
- Configure Open WebUI to use this server as its OpenAI API endpoint:
  - If Open WebUI is the container from this compose file, the OpenAI base URL should be:
    - `http://rag-api:8000/v1`

## Configure per machine (recommended)

Copy `.env.example` to `.env` and adjust as needed:

- `LM_STUDIO_BASE_URL`
- `LM_STUDIO_MODEL`
- `LM_STUDIO_EMBEDDING_MODEL`

Do not commit `.env`.

## Environment variables

- `QDRANT_URL` (default `http://qdrant:6333` when using Docker Compose)
- `QDRANT_API_KEY` (optional)
- `LM_STUDIO_BASE_URL` (default `http://localhost:1234/v1`)
- `LM_STUDIO_API_KEY` (default `lm-studio`)
- `LM_STUDIO_MODEL` (default `local-model`)

## Notes

- Uploads are stored under `data/uploads/<collection>/...`
- Each collection/topic is a separate Qdrant collection (e.g. `MTSS`)
