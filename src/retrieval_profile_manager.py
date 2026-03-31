from typing import Any, Dict, List, Optional
from datetime import datetime

from src.supabase_rest import SupabaseRestClient, SupabaseRestError
from src.retrieval_profiles import RetrievalProfile, BUILTIN_PROFILES


class RetrievalProfileManager:
    def __init__(self, supabase: Optional[SupabaseRestClient] = None):
        self._supabase = supabase
        self._cache: Dict[str, RetrievalProfile] = {}
    
    async def get_profile(self, profile_name: str) -> Optional[RetrievalProfile]:
        if profile_name in self._cache:
            return self._cache[profile_name]
        
        if profile_name in BUILTIN_PROFILES:
            profile = BUILTIN_PROFILES[profile_name]
            self._cache[profile_name] = profile
            return profile
        
        if not self._supabase:
            return None
        
        try:
            rows = await self._supabase.select(
                "RetrievalProfiles",
                filters={"profile_name": f"eq.{profile_name}"},
                limit=1,
            )
            
            if rows:
                profile = RetrievalProfile.from_dict(rows[0])
                self._cache[profile_name] = profile
                return profile
        except SupabaseRestError:
            pass
        
        return None
    
    async def list_profiles(self, include_inactive: bool = False) -> List[RetrievalProfile]:
        profiles = list(BUILTIN_PROFILES.values())
        
        if not self._supabase:
            return profiles
        
        try:
            filters = {} if include_inactive else {"is_active": "eq.true"}
            rows = await self._supabase.select(
                "RetrievalProfiles",
                filters=filters,
                order="created_at.desc",
            )
            
            for row in rows:
                profile = RetrievalProfile.from_dict(row)
                if not profile.is_system:
                    profiles.append(profile)
                    self._cache[profile.profile_name] = profile
        except SupabaseRestError:
            pass
        
        return profiles
    
    async def create_profile(self, profile: RetrievalProfile) -> RetrievalProfile:
        if not self._supabase:
            raise RuntimeError("Supabase is not configured")
        
        errors = profile.validate()
        if errors:
            raise ValueError(f"Invalid profile: {', '.join(errors)}")
        
        existing = await self.get_profile(profile.profile_name)
        if existing:
            raise ValueError(f"Profile '{profile.profile_name}' already exists")
        
        row = {
            "profile_name": profile.profile_name,
            "display_name": profile.display_name,
            "description": profile.description,
            "is_system": profile.is_system,
            "is_active": profile.is_active,
            "bm25_weight": profile.bm25_weight,
            "pg_fts_weight": profile.pg_fts_weight,
            "pg_vec_weight": profile.pg_vec_weight,
            "use_reranker": profile.use_reranker,
            "reranker_model": profile.reranker_model,
            "normalize_scores": profile.normalize_scores,
            "metadata_boost": profile.metadata_boost,
            "citation_graph_boost": profile.citation_graph_boost,
            "top_k": profile.top_k,
            "bm25_limit": profile.bm25_limit,
            "fts_limit": profile.fts_limit,
            "vec_limit": profile.vec_limit,
            "created_by": profile.created_by,
        }
        
        result = await self._supabase.insert("RetrievalProfiles", rows=[row])
        
        if result:
            created_profile = RetrievalProfile.from_dict(result[0])
            self._cache[created_profile.profile_name] = created_profile
            return created_profile
        
        return profile
    
    async def update_profile(self, profile_name: str, updates: Dict[str, Any]) -> Optional[RetrievalProfile]:
        if not self._supabase:
            raise RuntimeError("Supabase is not configured")
        
        existing = await self.get_profile(profile_name)
        if not existing:
            raise ValueError(f"Profile '{profile_name}' not found")
        
        if existing.is_system:
            raise ValueError(f"Cannot update system profile '{profile_name}'")
        
        allowed_fields = {
            "display_name", "description", "is_active",
            "bm25_weight", "pg_fts_weight", "pg_vec_weight",
            "use_reranker", "reranker_model", "normalize_scores",
            "metadata_boost", "citation_graph_boost",
            "top_k", "bm25_limit", "fts_limit", "vec_limit",
        }
        
        patch = {k: v for k, v in updates.items() if k in allowed_fields}
        
        if not patch:
            return existing
        
        result = await self._supabase.update(
            "RetrievalProfiles",
            patch=patch,
            filters={"profile_name": f"eq.{profile_name}"},
        )
        
        if result:
            updated_profile = RetrievalProfile.from_dict(result[0])
            self._cache[profile_name] = updated_profile
            return updated_profile
        
        return existing
    
    async def delete_profile(self, profile_name: str) -> bool:
        if not self._supabase:
            raise RuntimeError("Supabase is not configured")
        
        existing = await self.get_profile(profile_name)
        if not existing:
            return False
        
        if existing.is_system:
            raise ValueError(f"Cannot delete system profile '{profile_name}'")
        
        await self._supabase.delete(
            "RetrievalProfiles",
            filters={"profile_name": f"eq.{profile_name}"},
        )
        
        if profile_name in self._cache:
            del self._cache[profile_name]
        
        return True
    
    async def get_project_profile(self, collection: str) -> Optional[RetrievalProfile]:
        if not self._supabase:
            return await self.get_profile("balanced")
        
        try:
            rows = await self._supabase.select(
                "ProjectRetrievalSettings",
                filters={"collection": f"eq.{collection}"},
                limit=1,
            )
            
            if rows:
                row = rows[0]
                profile_name = row.get("profile_name")
                
                if profile_name:
                    return await self.get_profile(profile_name)
                
                custom_bm25 = row.get("custom_bm25_weight")
                custom_fts = row.get("custom_pg_fts_weight")
                custom_vec = row.get("custom_pg_vec_weight")
                
                if custom_bm25 is not None and custom_fts is not None and custom_vec is not None:
                    return RetrievalProfile(
                        profile_name="custom",
                        display_name="Custom",
                        description=f"Custom weights for {collection}",
                        is_system=False,
                        is_active=True,
                        bm25_weight=float(custom_bm25),
                        pg_fts_weight=float(custom_fts),
                        pg_vec_weight=float(custom_vec),
                        use_reranker=row.get("custom_use_reranker", False),
                        reranker_model=None,
                        normalize_scores=True,
                        metadata_boost=0.0,
                        citation_graph_boost=0.0,
                        top_k=10,
                        bm25_limit=30,
                        fts_limit=30,
                        vec_limit=30,
                    )
        except SupabaseRestError:
            pass
        
        return await self.get_profile("balanced")
    
    async def set_project_profile(self, collection: str, profile_name: str) -> bool:
        if not self._supabase:
            raise RuntimeError("Supabase is not configured")
        
        profile = await self.get_profile(profile_name)
        if not profile:
            raise ValueError(f"Profile '{profile_name}' not found")
        
        try:
            existing = await self._supabase.select(
                "ProjectRetrievalSettings",
                filters={"collection": f"eq.{collection}"},
                limit=1,
            )
            
            if existing:
                await self._supabase.update(
                    "ProjectRetrievalSettings",
                    patch={
                        "profile_name": profile_name,
                        "custom_bm25_weight": None,
                        "custom_pg_fts_weight": None,
                        "custom_pg_vec_weight": None,
                        "custom_use_reranker": None,
                    },
                    filters={"collection": f"eq.{collection}"},
                )
            else:
                await self._supabase.insert(
                    "ProjectRetrievalSettings",
                    rows=[{
                        "collection": collection,
                        "profile_name": profile_name,
                    }],
                )
            
            return True
        except SupabaseRestError:
            return False
    
    async def set_project_custom_weights(
        self,
        collection: str,
        bm25_weight: float,
        fts_weight: float,
        vec_weight: float,
        use_reranker: bool = False,
    ) -> bool:
        if not self._supabase:
            raise RuntimeError("Supabase is not configured")
        
        try:
            existing = await self._supabase.select(
                "ProjectRetrievalSettings",
                filters={"collection": f"eq.{collection}"},
                limit=1,
            )
            
            if existing:
                await self._supabase.update(
                    "ProjectRetrievalSettings",
                    patch={
                        "profile_name": None,
                        "custom_bm25_weight": bm25_weight,
                        "custom_pg_fts_weight": fts_weight,
                        "custom_pg_vec_weight": vec_weight,
                        "custom_use_reranker": use_reranker,
                    },
                    filters={"collection": f"eq.{collection}"},
                )
            else:
                await self._supabase.insert(
                    "ProjectRetrievalSettings",
                    rows=[{
                        "collection": collection,
                        "custom_bm25_weight": bm25_weight,
                        "custom_pg_fts_weight": fts_weight,
                        "custom_pg_vec_weight": vec_weight,
                        "custom_use_reranker": use_reranker,
                    }],
                )
            
            return True
        except SupabaseRestError:
            return False
