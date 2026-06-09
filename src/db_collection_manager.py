"""
Database-backed Collection Manager using Supabase
Replaces the file-based collection system with a proper database table
"""
import base64
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

from .supabase_rest import SupabaseRestClient


class DBCollectionManager:
    """Manages collections using Supabase database"""
    
    def __init__(self, supabase_client: SupabaseRestClient, storage_dir: Optional[Path] = None):
        self.supabase = supabase_client
        self.storage_dir = Path(storage_dir) if storage_dir else Path("collection_images")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def _sanitize_name(self, name: str) -> str:
        """Sanitize collection name for use as identifier"""
        sanitized = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name)
        return sanitized.lower().strip("_")
    
    async def create_collection(
        self,
        name: str,
        description: str = "",
        image_data: Optional[bytes] = None,
        image_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new collection in the database"""
        sanitized_name = self._sanitize_name(name)
        
        # Check if collection already exists
        existing = await self.supabase.select(
            "Collections",
            select="id,name",
            filters={"name": f"eq.{sanitized_name}"}
        )
        
        if existing:
            raise ValueError(f"Collection '{sanitized_name}' already exists")
        
        # Save image if provided
        image_url = None
        if image_data and image_filename:
            ext = Path(image_filename).suffix or ".jpg"
            image_path = self.storage_dir / f"{sanitized_name}{ext}"
            image_path.write_bytes(image_data)
            image_url = f"/collection-images/{sanitized_name}{ext}"
        
        # Insert into database
        collection_data = {
            "name": sanitized_name,
            "display_name": name,
            "description": description,
            "image_url": image_url
        }
        
        result = await self.supabase.insert("Collections", [collection_data])
        
        if not result:
            raise RuntimeError("Failed to create collection in database")
        
        return result[0]
    
    async def get_collection(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a collection by name"""
        result = await self.supabase.select(
            "Collections",
            select="*",
            filters={"name": f"eq.{name}"}
        )
        
        return result[0] if result else None
    
    async def get_collection_by_id(self, collection_id: str) -> Optional[Dict[str, Any]]:
        """Get a collection by ID"""
        result = await self.supabase.select(
            "Collections",
            select="*",
            filters={"id": f"eq.{collection_id}"}
        )
        
        return result[0] if result else None
    
    async def list_collections(self) -> List[Dict[str, Any]]:
        """List all collections with document counts"""
        collections = await self.supabase.select(
            "Collections",
            select="*",
            order="created_at.desc"
        )
        
        # Get document counts for each collection
        for coll in collections:
            # Count only completed documents (ingested and active)
            docs = await self.supabase.select(
                "Documents",
                select="id",
                filters={
                    "collection": f"eq.{coll['name']}",
                    "ingestion_status": "eq.complete",
                    "is_active": "eq.true"
                }
            )
            coll["file_count"] = len(docs) if docs else 0
        
        return collections
    
    async def update_collection(
        self,
        name: str,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        image_data: Optional[bytes] = None,
        image_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update collection metadata"""
        collection = await self.get_collection(name)
        
        if not collection:
            raise ValueError(f"Collection '{name}' not found")
        
        update_data = {}
        
        if display_name is not None:
            update_data["display_name"] = display_name
            
            # If display name changed, update the sanitized name too
            new_sanitized = self._sanitize_name(display_name)
            if new_sanitized != name:
                # Check if new name conflicts
                existing = await self.get_collection(new_sanitized)
                if existing and existing["id"] != collection["id"]:
                    raise ValueError(f"Collection '{new_sanitized}' already exists")
                update_data["name"] = new_sanitized
        
        if description is not None:
            update_data["description"] = description
        
        # Update image if provided
        if image_data and image_filename:
            ext = Path(image_filename).suffix or ".jpg"
            current_name = update_data.get("name", name)
            image_path = self.storage_dir / f"{current_name}{ext}"
            
            # Remove old image if exists
            if collection.get("image_url"):
                old_image_name = collection["image_url"].split("/")[-1]
                old_path = self.storage_dir / old_image_name
                if old_path.exists() and old_path != image_path:
                    old_path.unlink()
            
            image_path.write_bytes(image_data)
            update_data["image_url"] = f"/collection-images/{current_name}{ext}"
        
        if not update_data:
            return collection
        
        # Update in database
        result = await self.supabase.update(
            "Collections",
            patch=update_data,
            filters={"id": f"eq.{collection['id']}"}
        )
        
        if not result:
            raise RuntimeError("Failed to update collection")
        
        return result[0]
    
    async def delete_collection(self, name: str, delete_documents: bool = False) -> None:
        """Delete a collection"""
        collection = await self.get_collection(name)
        
        if not collection:
            raise ValueError(f"Collection '{name}' not found")
        
        # Delete image if exists
        if collection.get("image_url"):
            image_name = collection["image_url"].split("/")[-1]
            image_path = self.storage_dir / image_name
            if image_path.exists():
                image_path.unlink()
        
        if delete_documents:
            # Delete all documents in this collection
            await self.supabase.delete(
                "Documents",
                filters={"collection": f"eq.{name}"}
            )
            
            # Delete all chunks
            await self.supabase.delete(
                "DocumentChunks",
                filters={"collection": f"eq.{name}"}
            )
        
        # Delete collection
        await self.supabase.delete(
            "Collections",
            filters={"id": f"eq.{collection['id']}"}
        )
    
    def get_image_path(self, collection_name: str, image_url: str) -> Optional[Path]:
        """Get the file system path for a collection image"""
        if not image_url:
            return None
        
        image_name = image_url.split("/")[-1]
        image_path = self.storage_dir / image_name
        
        return image_path if image_path.exists() else None
