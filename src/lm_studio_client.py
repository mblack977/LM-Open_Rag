import os
from typing import Any, Dict, List, Optional

import httpx


class LMStudioClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: float = 120.0,
    ):
        # LM Studio exposes an OpenAI-compatible API.
        self._base_url = (base_url or os.getenv("LM_STUDIO_BASE_URL") or "http://localhost:1234/v1").rstrip("/")
        self._api_key = api_key or os.getenv("LM_STUDIO_API_KEY") or "lm-studio"
        self._model = model or os.getenv("LM_STUDIO_MODEL")
        self._timeout_seconds = timeout_seconds

    async def _resolve_model(self) -> str:
        if self._model:
            return self._model

        url = f"{self._base_url}/models"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        models = data.get("data") or []
        if not models:
            # Fallback to a common placeholder if the server returns no models.
            self._model = "local-model"
            return self._model

        # OpenAI-style payload: { data: [ { id: "..." }, ... ] }
        self._model = models[0].get("id") or "local-model"
        return self._model

    async def chat(self, messages: List[Dict[str, str]], temperature: float = 0.2, max_tokens: int = 800) -> str:
        url = f"{self._base_url}/chat/completions"
        model = await self._resolve_model()
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            resp = await client.post(url, headers=headers, json=payload)
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                body_text = e.response.text
                err_msg = None
                try:
                    j = e.response.json()
                    if isinstance(j, dict):
                        if isinstance(j.get("error"), dict) and isinstance(j["error"].get("message"), str):
                            err_msg = j["error"]["message"]
                        elif isinstance(j.get("message"), str):
                            err_msg = j.get("message")
                except Exception:
                    err_msg = None

                extra = err_msg or body_text
                raise RuntimeError(
                    f"LM Studio chat/completions returned HTTP {e.response.status_code}. "
                    f"Model: {model}. Response: {extra}"
                ) from e

            data = resp.json()

        # OpenAI-compatible response format
        return data["choices"][0]["message"]["content"]
