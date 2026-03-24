import os
from typing import Any, Dict, List, Optional

import httpx


class SupabaseRestError(RuntimeError):
    pass


class SupabaseRestClient:
    def __init__(
        self,
        supabase_url: Optional[str] = None,
        service_role_key: Optional[str] = None,
        timeout_seconds: float = 30.0,
    ):
        self._supabase_url = (supabase_url or os.getenv("SUPABASE_URL") or "").rstrip("/")
        self._service_role_key = service_role_key or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or ""
        self._timeout_seconds = timeout_seconds

        if not self._supabase_url:
            raise SupabaseRestError("SUPABASE_URL is not set")
        if not self._service_role_key:
            raise SupabaseRestError("SUPABASE_SERVICE_ROLE_KEY is not set")

        self._rest_url = f"{self._supabase_url}/rest/v1"

        self._rpc_url = f"{self._rest_url}/rpc"

    def _headers(self, prefer: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "apikey": self._service_role_key,
            "Authorization": f"Bearer {self._service_role_key}",
            "Content-Type": "application/json",
        }
        if isinstance(prefer, str) and prefer.strip():
            headers["Prefer"] = prefer
        return headers

    async def select(
        self,
        table: str,
        select: str = "*",
        filters: Optional[Dict[str, str]] = None,
        order: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        url = f"{self._rest_url}/{table}"
        params: Dict[str, Any] = {"select": select}
        if filters:
            params.update(filters)
        if isinstance(order, str) and order.strip():
            params["order"] = order
        if isinstance(limit, int):
            params["limit"] = str(limit)

        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            resp = await client.get(url, headers=self._headers(), params=params)

        if resp.status_code >= 400:
            raise SupabaseRestError(f"Supabase select failed ({resp.status_code}): {resp.text}")

        data = resp.json()
        if not isinstance(data, list):
            raise SupabaseRestError("Unexpected Supabase response (expected list)")
        return data

    async def insert(self, table: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        url = f"{self._rest_url}/{table}"
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            resp = await client.post(url, headers=self._headers(prefer="return=representation"), json=rows)

        if resp.status_code >= 400:
            raise SupabaseRestError(f"Supabase insert failed ({resp.status_code}): {resp.text}")

        data = resp.json()
        if not isinstance(data, list):
            raise SupabaseRestError("Unexpected Supabase response (expected list)")
        return data

    async def update(
        self,
        table: str,
        patch: Dict[str, Any],
        filters: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        url = f"{self._rest_url}/{table}"
        params: Dict[str, Any] = {}
        params.update(filters)

        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            resp = await client.patch(url, headers=self._headers(prefer="return=representation"), params=params, json=patch)

        if resp.status_code >= 400:
            raise SupabaseRestError(f"Supabase update failed ({resp.status_code}): {resp.text}")

        data = resp.json()
        if not isinstance(data, list):
            raise SupabaseRestError("Unexpected Supabase response (expected list)")
        return data

    async def delete(self, table: str, filters: Dict[str, str]) -> None:
        url = f"{self._rest_url}/{table}"
        params: Dict[str, Any] = {}
        params.update(filters)

        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            resp = await client.delete(url, headers=self._headers(), params=params)

        if resp.status_code >= 400:
            raise SupabaseRestError(f"Supabase delete failed ({resp.status_code}): {resp.text}")

    async def rpc(self, fn: str, payload: Optional[Dict[str, Any]] = None) -> Any:
        if not isinstance(fn, str) or not fn.strip():
            raise SupabaseRestError("RPC function name is required")

        url = f"{self._rpc_url}/{fn.strip()}"
        body = payload if isinstance(payload, dict) else {}

        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            resp = await client.post(url, headers=self._headers(), json=body)

        if resp.status_code >= 400:
            raise SupabaseRestError(f"Supabase rpc failed ({resp.status_code}): {resp.text}")

        # RPC can return list/object/scalar depending on function.
        try:
            return resp.json()
        except Exception as e:
            raise SupabaseRestError(f"Supabase rpc returned non-JSON response: {resp.text}") from e
