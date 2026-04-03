import logging
from typing import Any, Dict, List, Optional

from src.supabase_rest import SupabaseRestClient, SupabaseRestError

logger = logging.getLogger(__name__)


class ChatManager:
    def __init__(self, supabase: SupabaseRestClient):
        self._supabase = supabase

    async def create_session(self, title: str, collection: Optional[str]) -> Dict[str, Any]:
        try:
            row: Dict[str, Any] = {"title": title or "New Chat"}
            if collection:
                row["collection"] = collection
            rows = await self._supabase.insert("ChatSessions", rows=[row])
            return {"status": "success", "session": rows[0] if rows else None}
        except SupabaseRestError as e:
            logger.error(f"Error creating chat session: {e}")
            return {"status": "error", "message": str(e)}

    async def list_sessions(self, collection: Optional[str], limit: int = 50) -> Dict[str, Any]:
        try:
            filters: Dict[str, str] = {}
            if collection:
                filters["collection"] = f"eq.{collection}"
            rows = await self._supabase.select(
                "ChatSessions",
                select="*",
                filters=filters if filters else None,
                order="created_at.desc",
                limit=limit,
            )
            return {"status": "success", "sessions": rows}
        except SupabaseRestError as e:
            logger.error(f"Error listing chat sessions: {e}")
            return {"status": "error", "message": str(e)}

    async def get_session(self, session_id: str) -> Dict[str, Any]:
        try:
            rows = await self._supabase.select(
                "ChatSessions",
                select="*",
                filters={"id": f"eq.{session_id}"},
            )
            if not rows:
                return {"status": "error", "message": "Session not found"}
            return {"status": "success", "session": rows[0]}
        except SupabaseRestError as e:
            logger.error(f"Error getting chat session: {e}")
            return {"status": "error", "message": str(e)}

    async def update_session(self, session_id: str, title: Optional[str]) -> Dict[str, Any]:
        try:
            patch: Dict[str, Any] = {}
            if title is not None:
                patch["title"] = title
            if not patch:
                return {"status": "error", "message": "Nothing to update"}
            rows = await self._supabase.update(
                "ChatSessions",
                patch=patch,
                filters={"id": f"eq.{session_id}"},
            )
            return {"status": "success", "session": rows[0] if rows else None}
        except SupabaseRestError as e:
            logger.error(f"Error updating chat session: {e}")
            return {"status": "error", "message": str(e)}

    async def delete_session(self, session_id: str) -> Dict[str, Any]:
        try:
            await self._supabase.delete(
                "ChatMessages",
                filters={"session_id": f"eq.{session_id}"},
            )
            await self._supabase.delete(
                "ChatSessions",
                filters={"id": f"eq.{session_id}"},
            )
            return {"status": "success"}
        except SupabaseRestError as e:
            logger.error(f"Error deleting chat session: {e}")
            return {"status": "error", "message": str(e)}

    async def get_messages(self, session_id: str) -> Dict[str, Any]:
        try:
            rows = await self._supabase.select(
                "ChatMessages",
                select="*",
                filters={"session_id": f"eq.{session_id}"},
                order="created_at.asc",
            )
            return {"status": "success", "messages": rows}
        except SupabaseRestError as e:
            logger.error(f"Error getting chat messages: {e}")
            return {"status": "error", "message": str(e)}

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        sources: Optional[Any] = None,
        retrieval_profile: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            row: Dict[str, Any] = {
                "session_id": session_id,
                "role": role,
                "content": content,
            }
            if sources is not None:
                row["sources"] = sources
            if retrieval_profile is not None:
                row["retrieval_profile"] = retrieval_profile
            rows = await self._supabase.insert("ChatMessages", rows=[row])
            return {"status": "success", "message": rows[0] if rows else None}
        except SupabaseRestError as e:
            logger.error(f"Error adding chat message: {e}")
            return {"status": "error", "message": str(e)}
