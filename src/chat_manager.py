import logging
from typing import Any, Dict, List, Optional

from src.supabase_rest import SupabaseRestClient, SupabaseRestError

logger = logging.getLogger(__name__)


class ChatManager:
    def __init__(self, supabase: SupabaseRestClient):
        self._supabase = supabase

    def _generate_title_from_message(self, message: str) -> str:
        """Generate a short title from the first user message"""
        words = message.strip().split()
        if len(words) <= 6:
            return message
        return ' '.join(words[:6]) + '...'

    async def create_session(
        self, 
        title: Optional[str] = None, 
        collection: Optional[str] = None,
        user_id: str = "default_user"
    ) -> Dict[str, Any]:
        try:
            row: Dict[str, Any] = {
                "title": title or "New Chat",
                "user_id": user_id
            }
            if collection:
                row["collection"] = collection
            rows = await self._supabase.insert("ChatSessions", rows=[row])
            return {"status": "success", "session": rows[0] if rows else None}
        except SupabaseRestError as e:
            logger.error(f"Error creating chat session: {e}")
            return {"status": "error", "message": str(e)}

    async def list_sessions(
        self, 
        collection: Optional[str] = None, 
        limit: int = 50,
        user_id: str = "default_user"
    ) -> Dict[str, Any]:
        try:
            logger.info(f"list_sessions called: collection={collection}, limit={limit}, user_id={user_id}")
            filters: Dict[str, str] = {"user_id": f"eq.{user_id}"}
            if collection:
                filters["collection"] = f"eq.{collection}"
            
            logger.info(f"Querying ChatSessions with filters: {filters}")
            rows = await self._supabase.select(
                "ChatSessions",
                select="*",
                filters=filters,
                order="created_at.desc",
                limit=limit,
            )
            logger.info(f"✅ Listed {len(rows)} chat sessions for user {user_id}: {rows}")
            return {"status": "success", "sessions": rows}
        except SupabaseRestError as e:
            logger.error(f"❌ Error listing chat sessions: {e}")
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.error(f"❌ Unexpected error listing chat sessions: {e}")
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
        user_id: str = "default_user"
    ) -> Dict[str, Any]:
        try:
            row: Dict[str, Any] = {
                "session_id": session_id,
                "user_id": user_id,
                "role": role,
                "content": content,
            }
            if sources is not None:
                row["sources"] = sources
            if retrieval_profile is not None:
                row["retrieval_profile"] = retrieval_profile
            rows = await self._supabase.insert("ChatMessages", rows=[row])
            
            # Auto-generate title from first user message if session title is "New Chat"
            if role == "user":
                session_result = await self.get_session(session_id)
                if session_result.get("status") == "success":
                    session = session_result.get("session", {})
                    if session.get("title") == "New Chat" and session.get("message_count", 0) <= 1:
                        new_title = self._generate_title_from_message(content)
                        await self.update_session(session_id, new_title)
            
            return {"status": "success", "message": rows[0] if rows else None}
        except SupabaseRestError as e:
            logger.error(f"Error adding chat message: {e}")
            return {"status": "error", "message": str(e)}
