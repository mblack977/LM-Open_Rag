import asyncio
import os
from typing import Dict, List, Optional

import httpx
from sentence_transformers import SentenceTransformer


class EmbeddingGenerator:
    # Max concurrent requests to Ollama (single-prompt API, so parallelism matters)
    _OLLAMA_CONCURRENCY = 4

    # mxbai-embed-large has a strict 512-token context limit.
    # Dense academic text (statistics, citations) tokenises at 3-4 chars/token,
    # so 800 chars ≈ 200-270 tokens — safely under the cap.
    # Override with OLLAMA_EMBEDDING_MAX_CHARS for models with longer context (e.g. nomic-embed-text).
    _OLLAMA_MAX_CHARS = int(os.getenv("OLLAMA_EMBEDDING_MAX_CHARS") or "800")

    def __init__(self, model_name: Optional[str] = None):
        self._lm_base_url = (os.getenv("LM_STUDIO_BASE_URL") or "http://localhost:1234/v1").rstrip("/")
        self._lm_api_key = os.getenv("LM_STUDIO_API_KEY") or "lm-studio"
        self._lm_embedding_model = os.getenv("LM_STUDIO_EMBEDDING_MODEL")
        self._timeout_seconds = float(os.getenv("LM_STUDIO_TIMEOUT_SECONDS") or "120")
        self._batch_size = int(os.getenv("LM_STUDIO_EMBEDDING_BATCH_SIZE") or "16")

        self._ollama_base_url = (os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
        self._ollama_embedding_model = os.getenv("OLLAMA_EMBEDDING_MODEL")

        # LOCAL_EMBEDDING_MODEL lets you upgrade the local SentenceTransformer without code changes.
        # Recommended: BAAI/bge-base-en-v1.5 (768d) or BAAI/bge-large-en-v1.5 (1024d).
        # Changing this requires re-ingesting all documents (dimension change).
        local_model_name = (
            model_name
            or os.getenv("LOCAL_EMBEDDING_MODEL")
            or "sentence-transformers/all-MiniLM-L6-v2"
        )

        self._model_name = local_model_name
        self._model: Optional[SentenceTransformer] = None
        self._dimension_cache: Optional[int] = None

        if not self._lm_embedding_model and not self._ollama_embedding_model:
            self._model = SentenceTransformer(local_model_name)

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if self._ollama_embedding_model:
            vectors = await self._embed_texts_ollama_batched(texts)
            if vectors and self._dimension_cache is None:
                self._dimension_cache = len(vectors[0])
            return vectors

        if self._lm_embedding_model:
            vectors = await self._embed_texts_lm_studio_batched(texts)
            if vectors and self._dimension_cache is None:
                self._dimension_cache = len(vectors[0])
            return vectors

        return await asyncio.to_thread(self._embed_texts_sync, texts)

    async def embed_query(self, text: str) -> List[float]:
        vectors = await self.embed_texts([text])
        return vectors[0]

    def _embed_texts_sync(self, texts: List[str]) -> List[List[float]]:
        if self._model is None:
            raise RuntimeError("SentenceTransformer model is not initialized")
        embeddings = self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embeddings.tolist()

    # ── LM Studio ────────────────────────────────────────────────────────────

    async def _embed_texts_lm_studio_batched(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        batch_size = max(self._batch_size, 1)
        url = f"{self._lm_base_url}/embeddings"
        headers: Dict[str, str] = {
            "Authorization": f"Bearer {self._lm_api_key}",
            "Content-Type": "application/json",
        }
        out: List[List[float]] = []
        # One persistent client for the entire call — reuses TCP connection across batches.
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                out.extend(await self._call_lm_studio(client, url, headers, batch))
        return out

    async def _call_lm_studio(
        self,
        client: httpx.AsyncClient,
        url: str,
        headers: Dict[str, str],
        texts: List[str],
    ) -> List[List[float]]:
        payload = {"model": self._lm_embedding_model, "input": texts}
        try:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        except httpx.ConnectError as e:
            raise RuntimeError(
                f"Failed to connect to LM Studio embeddings endpoint at {url}. "
                "Ensure LM Studio's server is listening on 0.0.0.0 and the OpenAI-compatible server is enabled."
            ) from e
        except httpx.ReadTimeout as e:
            raise RuntimeError(
                f"Timed out calling LM Studio embeddings endpoint at {url}. "
                "Try increasing LM_STUDIO_TIMEOUT_SECONDS or reduce batch size."
            ) from e
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"LM Studio embeddings endpoint returned HTTP {e.response.status_code}. "
                f"Model: {self._lm_embedding_model}. Response: {e.response.text}"
            ) from e
        items = data.get("data") or []
        vectors = [it.get("embedding") for it in items]
        if not vectors or any(v is None for v in vectors):
            raise RuntimeError("LM Studio embeddings returned no vectors")
        return vectors

    # ── Ollama ───────────────────────────────────────────────────────────────

    async def _embed_texts_ollama_batched(self, texts: List[str]) -> List[List[float]]:
        """Use /api/embed (batch endpoint) with truncate:true — immune to context-length errors."""
        if not texts:
            return []
        url = f"{self._ollama_base_url}/api/embed"
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        batch_size = max(self._batch_size, 1)
        out: List[List[float]] = []
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            for i in range(0, len(texts), batch_size):
                batch = [t.replace("\x00", "")[:self._OLLAMA_MAX_CHARS] for t in texts[i : i + batch_size]]
                out.extend(await self._call_ollama_batch(client, url, headers, batch))
        return out

    async def _call_ollama_batch(
        self,
        client: httpx.AsyncClient,
        url: str,
        headers: Dict[str, str],
        texts: List[str],
    ) -> List[List[float]]:
        payload = {"model": self._ollama_embedding_model, "input": texts, "truncate": True}
        try:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        except httpx.ConnectError as e:
            raise RuntimeError(
                f"Failed to connect to Ollama at {url}. "
                "Ensure Ollama is running (ollama serve) and accessible."
            ) from e
        except httpx.ReadTimeout as e:
            raise RuntimeError(
                f"Timed out calling Ollama at {url}. "
                "Try increasing LM_STUDIO_TIMEOUT_SECONDS."
            ) from e
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"Ollama returned HTTP {e.response.status_code}. "
                f"Model: {self._ollama_embedding_model}. Response: {e.response.text}"
            ) from e
        # /api/embed returns {"embeddings": [[...], ...]}
        vectors = data.get("embeddings")
        if not vectors or any(v is None for v in vectors):
            raise RuntimeError("Ollama /api/embed returned no embeddings")
        return vectors

    # ── Helpers ──────────────────────────────────────────────────────────────

    @property
    def dimension(self) -> int:
        if self._dimension_cache is not None:
            return int(self._dimension_cache)
        if self._model is not None:
            return int(self._model.get_sentence_embedding_dimension())
        return 0
