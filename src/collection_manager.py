import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime


class CollectionManager:
    """Manages folder-based collections with metadata"""
    
    def __init__(self, collections_dir: Path):
        self._collections_dir = Path(collections_dir)
        self._collections_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_collection_path(self, collection_name: str) -> Path:
        """Get the folder path for a collection"""
        return self._collections_dir / collection_name
    
    def _get_metadata_path(self, collection_name: str) -> Path:
        """Get the metadata file path for a collection"""
        return self._get_collection_path(collection_name) / ".collection.json"
    
    def _sanitize_name(self, name: str) -> str:
        """Sanitize collection name for use as folder name"""
        # Replace spaces with underscores, remove special chars
        sanitized = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name)
        return sanitized.lower().strip("_")
    
    def create_collection(
        self,
        name: str,
        description: str = "",
        image_data: Optional[bytes] = None,
        image_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new collection with metadata"""
        sanitized_name = self._sanitize_name(name)
        collection_path = self._get_collection_path(sanitized_name)
        
        if collection_path.exists():
            raise ValueError(f"Collection '{sanitized_name}' already exists")
        
        # Create collection folder
        collection_path.mkdir(parents=True, exist_ok=True)
        
        # Save image if provided
        image_path = None
        if image_data and image_filename:
            ext = Path(image_filename).suffix or ".jpg"
            image_path = collection_path / f"cover{ext}"
            image_path.write_bytes(image_data)
        
        # Create metadata
        metadata = {
            "name": name,
            "sanitized_name": sanitized_name,
            "description": description,
            "image": f"cover{ext}" if image_path else None,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "file_count": 0,
        }
        
        # Save metadata
        metadata_path = self._get_metadata_path(sanitized_name)
        metadata_path.write_text(json.dumps(metadata, indent=2))
        
        return metadata
    
    def get_collection_metadata(self, collection_name: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a collection"""
        metadata_path = self._get_metadata_path(collection_name)
        
        if not metadata_path.exists():
            # Return basic metadata if no .collection.json exists
            collection_path = self._get_collection_path(collection_name)
            if collection_path.exists():
                files = list(collection_path.glob("*.pdf"))
                return {
                    "name": collection_name,
                    "sanitized_name": collection_name,
                    "description": "",
                    "image": None,
                    "created_at": None,
                    "updated_at": None,
                    "file_count": len(files),
                }
            return None
        
        try:
            metadata = json.loads(metadata_path.read_text())
            # Update file count
            collection_path = self._get_collection_path(collection_name)
            files = list(collection_path.glob("*.pdf"))
            metadata["file_count"] = len(files)
            return metadata
        except Exception:
            return None
    
    def update_collection_metadata(
        self,
        collection_name: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        image_data: Optional[bytes] = None,
        image_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update collection metadata and optionally rename folder"""
        metadata = self.get_collection_metadata(collection_name)
        collection_path = self._get_collection_path(collection_name)
        
        if not metadata:
            # Create folder if it doesn't exist (for old collections without folders)
            collection_path.mkdir(parents=True, exist_ok=True)
            
            # Create initial metadata for existing collection
            metadata = {
                "name": name or collection_name,
                "sanitized_name": collection_name,
                "description": description or "",
                "image": None,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
                "file_count": len(list(collection_path.glob("*.pdf"))),
            }
        
        old_collection_path = self._get_collection_path(collection_name)
        new_sanitized_name = collection_name
        
        # Check if name is changing and handle folder rename
        if name is not None and name != metadata.get("name"):
            new_sanitized_name = self._sanitize_name(name)
            new_collection_path = self._get_collection_path(new_sanitized_name)
            
            # Check if new name conflicts with existing collection
            if new_collection_path.exists() and new_collection_path != old_collection_path:
                raise ValueError(f"Collection '{new_sanitized_name}' already exists")
            
            # Rename folder if sanitized name changed
            if new_sanitized_name != collection_name:
                old_collection_path.rename(new_collection_path)
                old_collection_path = new_collection_path
            
            metadata["name"] = name
            metadata["sanitized_name"] = new_sanitized_name
        
        # Update description
        if description is not None:
            metadata["description"] = description
        
        # Update image if provided
        if image_data and image_filename:
            collection_path = self._get_collection_path(new_sanitized_name)
            ext = Path(image_filename).suffix or ".jpg"
            image_path = collection_path / f"cover{ext}"
            
            # Remove old image if different extension
            if metadata.get("image"):
                old_image = collection_path / metadata["image"]
                if old_image.exists() and old_image != image_path:
                    old_image.unlink()
            
            image_path.write_bytes(image_data)
            metadata["image"] = f"cover{ext}"
        
        metadata["updated_at"] = datetime.utcnow().isoformat()
        
        # Save metadata
        metadata_path = self._get_metadata_path(new_sanitized_name)
        metadata_path.write_text(json.dumps(metadata, indent=2))
        
        return metadata
    
    def list_collections(self) -> List[Dict[str, Any]]:
        """List all collections with metadata"""
        collections = []
        
        for collection_path in self._collections_dir.iterdir():
            if collection_path.is_dir():
                metadata = self.get_collection_metadata(collection_path.name)
                if metadata:
                    collections.append(metadata)
        
        # Sort by creation date (newest first)
        collections.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        return collections
    
    def delete_collection(self, collection_name: str, delete_files: bool = False) -> None:
        """Delete a collection and optionally its files"""
        collection_path = self._get_collection_path(collection_name)
        
        if not collection_path.exists():
            raise ValueError(f"Collection '{collection_name}' not found")
        
        if delete_files:
            # Delete entire folder
            shutil.rmtree(collection_path)
        else:
            # Only delete metadata, keep files
            metadata_path = self._get_metadata_path(collection_name)
            if metadata_path.exists():
                metadata_path.unlink()
    
    def get_collection_files(self, collection_name: str) -> List[Path]:
        """Get all PDF files in a collection"""
        collection_path = self._get_collection_path(collection_name)
        
        if not collection_path.exists():
            return []
        
        return list(collection_path.glob("*.pdf"))
    
    def get_collection_image_path(self, collection_name: str) -> Optional[Path]:
        """Get the path to the collection's cover image"""
        metadata = self.get_collection_metadata(collection_name)
        if not metadata or not metadata.get("image"):
            return None
        
        collection_path = self._get_collection_path(collection_name)
        image_path = collection_path / metadata["image"]
        
        return image_path if image_path.exists() else None
