import asyncio
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm


class VectorStore:
    def __init__(
        self,
        qdrant_url: Optional[str] = None,
        api_key: Optional[str] = None,
        data_dir: Optional[Path] = None,
    ):
        self._qdrant_url = qdrant_url or os.getenv("QDRANT_URL") or "http://localhost:6333"
        self._api_key = api_key or os.getenv("QDRANT_API_KEY")
        self._vector_name_override = os.getenv("QDRANT_VECTOR_NAME")
        self._client = QdrantClient(url=self._qdrant_url, api_key=self._api_key)
        self._data_dir = Path(data_dir) if data_dir is not None else None

    async def list_collections(self) -> List[str]:
        return await asyncio.to_thread(self._list_collections_sync)

    def _list_collections_sync(self) -> List[str]:
        cols = self._client.get_collections().collections
        return [c.name for c in cols]

    async def ensure_collection(self, collection: str, vector_size: int) -> None:
        await asyncio.to_thread(self._ensure_collection_sync, collection, vector_size)

    async def get_vector_name(self, collection: str) -> Optional[str]:
        return await asyncio.to_thread(self._get_vector_name_sync, collection)

    async def get_vector_size(self, collection: str, vector_name: Optional[str]) -> Optional[int]:
        return await asyncio.to_thread(self._get_vector_size_sync, collection, vector_name)

    def _ensure_collection_sync(self, collection: str, vector_size: int) -> None:
        existing = set(self._list_collections_sync())
        if collection in existing:
            return

        self._client.create_collection(
            collection_name=collection,
            vectors_config={
                "text": qm.VectorParams(size=vector_size, distance=qm.Distance.COSINE),
            },
        )

        # Payload indexes for faster filtering
        self._client.create_payload_index(
            collection_name=collection,
            field_name="doc_id",
            field_schema=qm.PayloadSchemaType.KEYWORD,
        )
        self._client.create_payload_index(
            collection_name=collection,
            field_name="filename",
            field_schema=qm.PayloadSchemaType.KEYWORD,
        )

    def _get_collection_json_sync(self, collection: str) -> Dict[str, Any]:
        """Fetch raw collection info from Qdrant REST API.

        This avoids qdrant-client/Pydantic parsing issues when Qdrant server returns
        newer fields than the installed client models.
        """
        url = self._qdrant_url.rstrip("/") + f"/collections/{collection}"
        headers: Dict[str, str] = {}
        if isinstance(self._api_key, str) and self._api_key.strip():
            headers["api-key"] = self._api_key.strip()

        with httpx.Client(timeout=30.0) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        if not isinstance(data, dict):
            raise RuntimeError("Unexpected Qdrant response when reading collection info")
        return data

    def _get_vector_name_sync(self, collection: str) -> Optional[str]:
        if isinstance(self._vector_name_override, str) and self._vector_name_override.strip():
            return self._vector_name_override.strip()

        data = self._get_collection_json_sync(collection)
        result = data.get("result") if isinstance(data, dict) else None
        if not isinstance(result, dict):
            return None

        vectors = result
        for key in ["config", "params", "vectors"]:
            if isinstance(vectors, dict) and key in vectors:
                vectors = vectors.get(key)

        # Unnamed vector case: {"size": 1024, "distance": "Cosine", ...}
        if isinstance(vectors, dict) and "size" in vectors:
            return None

        # Named vectors case: {"text": {"size": ...}, "mtss-dense": {...}}
        if isinstance(vectors, dict) and vectors:
            if "text" in vectors:
                return "text"
            name = next(iter(vectors.keys()), None)
            if isinstance(name, str) and not name.strip():
                return None
            return name if isinstance(name, str) else None

        return None

    def _get_vector_size_sync(self, collection: str, vector_name: Optional[str]) -> Optional[int]:
        data = self._get_collection_json_sync(collection)
        result = data.get("result") if isinstance(data, dict) else None
        if not isinstance(result, dict):
            return None

        vectors: Any = result
        for key in ["config", "params", "vectors"]:
            if isinstance(vectors, dict) and key in vectors:
                vectors = vectors.get(key)

        # Unnamed vector: {"size": ...}
        if isinstance(vectors, dict) and "size" in vectors:
            try:
                return int(vectors.get("size"))
            except Exception:
                return None

        # Named vectors: {"text": {"size": ...}, ...}
        if isinstance(vectors, dict) and vector_name and vector_name in vectors:
            params = vectors.get(vector_name)
            if isinstance(params, dict) and "size" in params:
                try:
                    return int(params.get("size"))
                except Exception:
                    return None

        if isinstance(vectors, dict) and "text" in vectors:
            params = vectors.get("text")
            if isinstance(params, dict) and "size" in params:
                try:
                    return int(params.get("size"))
                except Exception:
                    return None

        return None

    async def upsert_chunks(
        self,
        collection: str,
        points: List[qm.PointStruct],
    ) -> None:
        await asyncio.to_thread(self._upsert_chunks_sync, collection, points)

    def _upsert_chunks_sync(self, collection: str, points: List[qm.PointStruct]) -> None:
        self._client.upsert(collection_name=collection, points=points)

    async def search(
        self,
        collection: str,
        query_vector: List[float],
        limit: int = 6,
        doc_id: Optional[str] = None,
        vector_name: Optional[str] = None,
    ) -> List[qm.ScoredPoint]:
        return await asyncio.to_thread(self._search_sync, collection, query_vector, limit, doc_id, vector_name)

    def _search_sync(
        self,
        collection: str,
        query_vector: List[float],
        limit: int,
        doc_id: Optional[str],
        vector_name: Optional[str],
    ) -> List[qm.ScoredPoint]:
        flt = None
        if doc_id is not None:
            flt = qm.Filter(must=[qm.FieldCondition(key="doc_id", match=qm.MatchValue(value=doc_id))])

        qv: Any = query_vector
        if vector_name:
            qv = qm.NamedVector(name=vector_name, vector=query_vector)

        return self._client.search(
            collection_name=collection,
            query_vector=qv,
            limit=limit,
            query_filter=flt,
            with_payload=True,
        )

    async def scroll_all_payload(self, collection: str, limit: int = 256) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self._scroll_all_payload_sync, collection, limit)

    def _scroll_all_payload_sync(self, collection: str, limit: int) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        next_page = None
        while True:
            points, next_page = self._client.scroll(
                collection_name=collection,
                scroll_filter=None,
                limit=limit,
                with_payload=True,
                with_vectors=False,
                offset=next_page,
            )
            for p in points:
                if p.payload is not None:
                    out.append(dict(p.payload))
            if next_page is None:
                break
        return out

    async def delete_by_doc_id(self, collection: str, doc_id: str) -> None:
        await asyncio.to_thread(self._delete_by_doc_id_sync, collection, doc_id)

    def _delete_by_doc_id_sync(self, collection: str, doc_id: str) -> None:
        flt = qm.Filter(must=[qm.FieldCondition(key="doc_id", match=qm.MatchValue(value=doc_id))])
        self._client.delete(collection_name=collection, points_selector=qm.FilterSelector(filter=flt))
