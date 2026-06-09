import logging
import re
from datetime import date
from typing import Any, Dict, List, Optional

import httpx

from src.supabase_rest import SupabaseRestClient, SupabaseRestError

logger = logging.getLogger(__name__)

CROSSREF_BASE = "https://api.crossref.org/works"
MIN_FUZZY_SCORE = 1.5


class CrossRefEnricher:
    def __init__(self, supabase: SupabaseRestClient, mailto: str = ""):
        self._supabase = supabase
        user_agent = f"HerbGPT/1.0 (mailto:{mailto})" if mailto else "HerbGPT/1.0"
        self._headers = {"User-Agent": user_agent}

    # ── CrossRef API ──────────────────────────────────────────────────────────

    async def lookup_by_doi(self, doi: str) -> Optional[Dict[str, Any]]:
        """Exact DOI lookup. Returns parsed metadata or None."""
        url = f"{CROSSREF_BASE}/{doi.strip()}"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, headers=self._headers)
            if resp.status_code == 404:
                return None
            if resp.status_code >= 400:
                logger.warning(f"CrossRef DOI lookup {resp.status_code}: {doi}")
                return None
            return self._parse_work(resp.json().get("message", {}))
        except Exception as e:
            logger.error(f"CrossRef DOI error for {doi!r}: {e}")
            return None

    async def lookup_by_metadata(
        self,
        title: str,
        author: Optional[str] = None,
        year: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Fuzzy title/author search. Returns best match if score >= MIN_FUZZY_SCORE."""
        params: Dict[str, Any] = {
            "query.title": title,
            "rows": 3,
            "select": "DOI,title,author,published,published-print,abstract,type,"
                      "container-title,volume,issue,page,publisher,score",
        }
        if author:
            params["query.author"] = author
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(CROSSREF_BASE, params=params, headers=self._headers)
            if resp.status_code >= 400:
                logger.warning(f"CrossRef fuzzy lookup {resp.status_code}")
                return None
            items = resp.json().get("message", {}).get("items", [])
            if not items:
                return None
            best = items[0]
            score = best.get("score", 0)
            if score < MIN_FUZZY_SCORE:
                logger.info(f"CrossRef fuzzy score too low ({score:.2f}) for: {title!r}")
                return None
            parsed = self._parse_work(best)
            parsed["_match_score"] = score
            return parsed
        except Exception as e:
            logger.error(f"CrossRef fuzzy error for {title!r}: {e}")
            return None

    # ── Enrichment actions ────────────────────────────────────────────────────

    async def enrich_document(
        self,
        document_id: int,
        overwrite: bool = False,
    ) -> Dict[str, Any]:
        """Look up CrossRef and write any new metadata to Documents row."""
        rows = await self._supabase.select(
            "Documents",
            select="*",
            filters={"id": f"eq.{document_id}"},
        )
        if not rows:
            return {"status": "error", "message": "Document not found"}
        doc = rows[0]

        doi = (doc.get("doi") or "").strip()
        title = doc.get("title") or ""
        match_score: Optional[float] = None

        if doi:
            meta = await self.lookup_by_doi(doi)
            match_score = 1.0
        elif title:
            meta = await self.lookup_by_metadata(title, doc.get("author"), doc.get("year"))
            if meta:
                match_score = meta.pop("_match_score", None)
        else:
            return {
                "status": "skipped",
                "message": "No DOI or title available",
                "document_id": document_id,
            }

        if meta is None:
            await self._supabase.update(
                "Documents",
                patch={"processing_error": "CrossRef lookup returned no results", "needs_review": True},
                filters={"id": f"eq.{document_id}"},
            )
            return {"status": "not_found", "document_id": document_id}

        # Build patch — skip fields that already have values unless overwrite=True
        enrichable = ["doi", "title", "author", "year", "abstract", "document_type", "apa7_reference"]
        patch: Dict[str, Any] = {}
        for field in enrichable:
            val = meta.get(field)
            if val and (overwrite or not doc.get(field)):
                patch[field] = val

        # Stamp tags
        existing = doc.get("tags") or []
        if not isinstance(existing, list):
            existing = []
        clean = [t for t in existing if not (isinstance(t, str) and t.startswith("crossref_"))]
        clean.append("crossref_enriched")
        clean.append(f"crossref_date:{date.today().isoformat()}")
        if match_score is not None:
            clean.append(f"crossref_score:{match_score:.2f}")
        patch["tags"] = clean
        patch["needs_review"] = False
        patch["processing_error"] = None

        merged = {**doc, **patch}
        patch["metadata_complete"] = self._is_metadata_complete(merged)

        await self._supabase.update("Documents", patch=patch, filters={"id": f"eq.{document_id}"})

        return {
            "status": "enriched",
            "document_id": document_id,
            "fields_updated": [k for k in patch if k not in ("tags", "needs_review", "processing_error", "metadata_complete")],
            "match_score": match_score,
        }

    async def enrich_collection(
        self,
        collection: Optional[str] = None,
        overwrite: bool = False,
        limit: int = 200,
    ) -> Dict[str, Any]:
        """Batch-enrich documents that are missing metadata."""
        filters: Dict[str, str] = {"is_active": "eq.true"}
        if collection:
            filters["collection"] = f"eq.{collection}"
        if not overwrite:
            filters["metadata_complete"] = "eq.false"

        rows = await self._supabase.select(
            "Documents",
            select="id",
            filters=filters,
            limit=limit,
        )

        counts: Dict[str, int] = {"enriched": 0, "skipped": 0, "not_found": 0, "errors": 0}
        details: List[Dict[str, Any]] = []

        for row in rows:
            doc_id = row["id"]
            try:
                result = await self.enrich_document(doc_id, overwrite=overwrite)
                s = result.get("status", "error")
                bucket = s if s in counts else "errors"
                counts[bucket] += 1
                details.append({"id": doc_id, **result})
            except Exception as e:
                logger.error(f"Error enriching document {doc_id}: {e}")
                counts["errors"] += 1
                details.append({"id": doc_id, "status": "error", "message": str(e)})

        return {
            "status": "complete",
            "collection": collection,
            **counts,
            "details": details,
        }

    async def preview_document(self, document_id: int) -> Dict[str, Any]:
        """Return what CrossRef would provide without writing anything."""
        rows = await self._supabase.select(
            "Documents",
            select="id,doi,title,author,year",
            filters={"id": f"eq.{document_id}"},
        )
        if not rows:
            return {"status": "error", "message": "Document not found"}
        doc = rows[0]

        doi = (doc.get("doi") or "").strip()
        if doi:
            meta = await self.lookup_by_doi(doi)
            method = "doi"
        elif doc.get("title"):
            meta = await self.lookup_by_metadata(doc["title"], doc.get("author"), doc.get("year"))
            method = "fuzzy"
            if meta:
                meta.pop("_match_score", None)
        else:
            return {"status": "skipped", "message": "No DOI or title"}

        return {
            "status": "found" if meta else "not_found",
            "method": method,
            "document_id": document_id,
            "crossref_data": meta,
        }

    # ── Parsers ───────────────────────────────────────────────────────────────

    def _parse_work(self, work: Dict[str, Any]) -> Dict[str, Any]:
        """Normalise a CrossRef work object into our field names."""
        titles = work.get("title") or []
        title = titles[0] if titles else ""

        raw_authors = work.get("author") or []
        author_parts: List[str] = []
        for a in raw_authors:
            family = a.get("family", "")
            given = a.get("given", "")
            if family:
                entry = f"{family}, {given}".strip(", ")
                author_parts.append(entry)
        author_str = "; ".join(author_parts)

        year: Optional[int] = None
        for pub_key in ("published", "published-print", "published-online"):
            pub = work.get(pub_key)
            if pub:
                dp = pub.get("date-parts", [[]])
                if dp and dp[0]:
                    year = dp[0][0]
                    break

        abstract = work.get("abstract", "")
        if abstract:
            abstract = re.sub(r"<[^>]+>", "", abstract).strip()

        type_map = {
            "journal-article": "journal_article",
            "book-chapter": "book_chapter",
            "book": "book",
            "proceedings-article": "conference_paper",
            "dissertation": "thesis",
            "report": "report",
            "preprint": "preprint",
        }
        doc_type = type_map.get(work.get("type", ""), work.get("type", ""))

        doi = work.get("DOI", "")
        journal = (work.get("container-title") or [""])[0]
        volume = work.get("volume", "")
        issue = work.get("issue", "")
        page = work.get("page", "")

        apa7 = self._build_apa7(author_parts, year, title, journal, volume, issue, page, doi)

        return {
            "doi": doi,
            "title": title,
            "author": author_str,
            "year": year,
            "abstract": abstract,
            "document_type": doc_type,
            "journal": journal,
            "volume": volume,
            "issue": issue,
            "page": page,
            "publisher": work.get("publisher", ""),
            "apa7_reference": apa7,
        }

    def _build_apa7(
        self,
        author_parts: List[str],
        year: Optional[int],
        title: str,
        journal: str,
        volume: str,
        issue: str,
        page: str,
        doi: str,
    ) -> str:
        """APA 7th edition reference string."""
        apa_authors: List[str] = []
        for a in author_parts[:20]:
            parts = a.split(", ", 1)
            family = parts[0]
            given = parts[1] if len(parts) > 1 else ""
            initials = ". ".join(n[0] for n in given.split() if n)
            if initials:
                initials += "."
            apa_authors.append(f"{family}, {initials}".strip(", "))

        if len(author_parts) > 20:
            apa_authors = apa_authors[:19] + ["..."] + [apa_authors[-1]]

        author_str = ", ".join(apa_authors) if apa_authors else "(No author)"
        year_str = f"({year})" if year else "(n.d.)"

        ref = f"{author_str}. {year_str}. {title}."
        if journal:
            vol_issue = f"{volume}" if volume else ""
            if issue:
                vol_issue += f"({issue})"
            page_str = f", {page}" if page else ""
            ref += f" {journal}, {vol_issue}{page_str}."
        if doi:
            ref += f" https://doi.org/{doi}"

        return ref

    def _is_metadata_complete(self, doc: Dict[str, Any]) -> bool:
        required = ["title", "filename", "collection", "doc_id", "source_type"]
        if not all(doc.get(f) for f in required):
            return False
        score = sum(1 for f in ["author", "year", "document_type", "abstract"] if doc.get(f))
        return score >= 2
