import asyncio
import os
from typing import List, Optional

import httpx
from sentence_transformers import SentenceTransformer


class EmbeddingGenerator:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self._lm_base_url = (os.getenv("LM_STUDIO_BASE_URL") or "http://localhost:1234/v1").rstrip("/")
        self._lm_api_key = os.getenv("LM_STUDIO_API_KEY") or "lm-studio"
        self._lm_embedding_model = os.getenv("LM_STUDIO_EMBEDDING_MODEL")
        self._timeout_seconds = float(os.getenv("LM_STUDIO_TIMEOUT_SECONDS") or "120")
        self._batch_size = int(os.getenv("LM_STUDIO_EMBEDDING_BATCH_SIZE") or "16")
        
        self._ollama_base_url = (os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
        self._ollama_embedding_model = os.getenv("OLLAMA_EMBEDDING_MODEL")

        self._model_name = model_name
        self._model: Optional[SentenceTransformer] = None
        self._dimension_cache: Optional[int] = None

        if not self._lm_embedding_model and not self._ollama_embedding_model:
            self._model = SentenceTransformer(model_name)

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

    async def _embed_texts_lm_studio_batched(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        batch_size = self._batch_size
        if batch_size <= 0:
            batch_size = 16

        out: List[List[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            out.extend(await self._embed_texts_lm_studio(batch))
        return out

    async def _embed_texts_lm_studio(self, texts: List[str]) -> List[List[float]]:
        url = f"{self._lm_base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self._lm_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._lm_embedding_model,
            "input": texts,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.ConnectError as e:
            raise RuntimeError(
                f"Failed to connect to LM Studio embeddings endpoint at {url}. "
                "If you are running this inside Docker, ensure LM Studio's server is listening on 0.0.0.0 (not only 127.0.0.1) "
                "and that the OpenAI-compatible server is enabled."
            ) from e
        except httpx.ReadTimeout as e:
            raise RuntimeError(
                f"Timed out calling LM Studio embeddings endpoint at {url}. "
                "Try increasing LM_STUDIO_TIMEOUT_SECONDS or reduce batch size."
            ) from e
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"LM Studio embeddings endpoint returned HTTP {e.response.status_code} at {url}. "
                f"Model: {self._lm_embedding_model}. Response: {e.response.text}"
            ) from e

        # OpenAI-style response: { data: [ { embedding: [...] }, ... ] }
        items = data.get("data") or []
        vectors = [it.get("embedding") for it in items]
        if not vectors or any(v is None for v in vectors):
            raise RuntimeError("LM Studio embeddings returned no vectors")
        return vectors

    async def _embed_texts_ollama_batched(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        out: List[List[float]] = []
        for text in texts:
            vector = await self._embed_text_ollama(text)
            out.append(vector)
        return out

    async def _embed_text_ollama(self, text: str) -> List[float]:
        url = f"{self._ollama_base_url}/api/embeddings"
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": self._ollama_embedding_model,
            "prompt": text,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.ConnectError as e:
            raise RuntimeError(
                f"Failed to connect to Ollama embeddings endpoint at {url}. "
                "Ensure Ollama is running (ollama serve) and accessible."
            ) from e
        except httpx.ReadTimeout as e:
            raise RuntimeError(
                f"Timed out calling Ollama embeddings endpoint at {url}. "
                "Try increasing LM_STUDIO_TIMEOUT_SECONDS."
            ) from e
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"Ollama embeddings endpoint returned HTTP {e.response.status_code} at {url}. "
                f"Model: {self._ollama_embedding_model}. Response: {e.response.text}"
            ) from e

        # Ollama response: { embedding: [...] }
        vector = data.get("embedding")
        if not vector:
            raise RuntimeError("Ollama embeddings returned no vector")
        return vector

    @property
    def dimension(self) -> int:
        if self._dimension_cache is not None:
            return int(self._dimension_cache)
        if self._model is not None:
            return int(self._model.get_sentence_embedding_dimension())
        # If using LM Studio embeddings, dimension is unknown until first call.
        # This will be filled after the first embed_texts/embed_query.
        return 0
