"""
sync_collection.py — Two-phase sync for a HerbGPT collection.

  Phase 1: Ingest all files on disk through the full pipeline
           (Qdrant vectors + Supabase Documents + Chunks).
  Phase 2: Update each document's metadata from document_import.csv
           (title, authors, abstract, year, DOI).

Usage:
    python sync_collection.py [collection]
    python sync_collection.py herbgpt        # default
"""

import csv
import os
import re
import sys
import time
from pathlib import Path

import httpx

sys.stdout.reconfigure(encoding="utf-8")

# ── Configuration ─────────────────────────────────────────────────────────────
COLLECTION    = sys.argv[1] if len(sys.argv) > 1 else "herbgpt"
SERVER_URL    = "http://localhost:8010"
UPLOADS_DIR   = Path(__file__).parent / "data" / "uploads" / COLLECTION
CSV_PATH      = UPLOADS_DIR / "document_import.csv"
SUPPORTED_EXT = {".pdf", ".txt", ".docx", ".md"}


def _load_env() -> dict:
    env_path = Path(__file__).parent / ".env"
    result = {}
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    result[k.strip()] = v.strip()
    return result


_ENV = _load_env()
_SB_URL = (_ENV.get("SUPABASE_URL") or "").rstrip("/")
_SB_KEY = _ENV.get("SUPABASE_SERVICE_ROLE_KEY") or ""
_SB_HEADERS = {
    "apikey": _SB_KEY,
    "Authorization": f"Bearer {_SB_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


def _normalise(text: str) -> str:
    """Lowercase, strip punctuation/whitespace for fuzzy matching."""
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


def _match_csv_to_doc(csv_title: str, docs: list) -> dict | None:
    """
    Find the best-matching doc for a CSV title.
    Strategy: the first ~60 normalised chars of the title should appear
    at the start of the normalised filename.
    """
    norm_title = _normalise(csv_title)[:60]
    best, best_score = None, 0

    for doc in docs:
        fname = _normalise(doc.get("filename", "") or "")
        if norm_title and fname.startswith(norm_title[:30]):
            score = len(norm_title)
            if score > best_score:
                best, best_score = doc, score

    # Fallback: title appears anywhere in the filename
    if best is None:
        title_words = norm_title.split()[:6]
        for doc in docs:
            fname = _normalise(doc.get("filename", "") or "")
            hits = sum(1 for w in title_words if w in fname)
            if hits >= max(3, len(title_words) // 2) and hits > best_score:
                best, best_score = doc, hits

    return best


# ── Phase 1: Ingest ──────────────────────────────────────────────────────────

def fetch_existing_filenames() -> set[str]:
    """Return filenames that already have a record in Supabase (direct query)."""
    if not _SB_URL or not _SB_KEY:
        print("  Warning: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set — falling back to app server")
        return _fetch_existing_via_server()
    try:
        resp = httpx.get(
            f"{_SB_URL}/rest/v1/Documents",
            headers={k: v for k, v in _SB_HEADERS.items() if k != "Prefer"},
            params={"select": "filename", "collection": f"eq.{COLLECTION}"},
            timeout=30.0,
        )
        if resp.status_code == 200:
            rows = resp.json()
            if isinstance(rows, list):
                return {r.get("filename", "") for r in rows if r.get("filename")}
    except Exception as exc:
        print(f"  Warning: could not fetch existing records — {exc}")
    return set()


def _fetch_existing_via_server() -> set[str]:
    try:
        resp = httpx.get(
            f"{SERVER_URL}/documents",
            params={"collection": COLLECTION},
            timeout=30.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            docs = data.get("documents") if isinstance(data, dict) else data
            if isinstance(docs, list):
                return {d.get("filename", "") for d in docs if d.get("filename")}
    except Exception as exc:
        print(f"  Warning: server fetch failed — {exc}")
    return set()


def ingest_all(files: list[Path]) -> dict[str, str]:
    """POST each file to /upload, skipping files already fully ingested."""
    print(f"\n{'='*60}")
    print(f"PHASE 1 — Checking {len(files)} files for '{COLLECTION}'")
    print(f"{'='*60}\n")

    existing = fetch_existing_filenames()
    print(f"Already complete in Supabase: {len(existing)} file(s) — skipping these.\n")

    to_ingest = [fp for fp in files if fp.name not in existing]
    if not to_ingest:
        print("All files already ingested — nothing to do.\n")
        return {}

    ingested: dict[str, str] = {}
    ok, failed = 0, 0

    for i, fp in enumerate(to_ingest, 1):
        print(f"[{i:>2}/{len(to_ingest)}] {fp.name[:70]:<70} ", end="", flush=True)
        try:
            with open(fp, "rb") as fh:
                resp = httpx.post(
                    f"{SERVER_URL}/upload",
                    data={"collection": COLLECTION},
                    files={"file": (fp.name, fh, "application/octet-stream")},
                    timeout=300.0,
                )
            if resp.status_code == 200:
                data = resp.json()
                doc_id = data.get("result", {}).get("doc_id", "")
                ingested[fp.name] = doc_id
                print("OK")
                ok += 1
            else:
                print(f"FAILED ({resp.status_code})")
                failed += 1
        except Exception as exc:
            print(f"ERROR: {exc}")
            failed += 1
        time.sleep(0.2)

    print(f"\nPhase 1 done: {ok} ingested, {failed} failed.\n")
    return ingested


# ── Phase 2: Metadata ────────────────────────────────────────────────────────

def fetch_documents() -> list:
    """Fetch all documents for the collection directly from Supabase."""
    if not _SB_URL or not _SB_KEY:
        return _fetch_documents_via_server()
    try:
        resp = httpx.get(
            f"{_SB_URL}/rest/v1/Documents",
            headers={k: v for k, v in _SB_HEADERS.items() if k != "Prefer"},
            params={
                "select": "doc_id,filename,title,authors,abstract,notes,year,doi",
                "collection": f"eq.{COLLECTION}",
                "order": "created_at.desc",
            },
            timeout=30.0,
        )
        if resp.status_code == 200:
            rows = resp.json()
            if isinstance(rows, list):
                return rows
        print(f"  Warning: Supabase fetch returned {resp.status_code}")
    except Exception as exc:
        print(f"  Warning: could not fetch documents — {exc}")
    return []


def _fetch_documents_via_server() -> list:
    try:
        resp = httpx.get(
            f"{SERVER_URL}/documents",
            params={"collection": COLLECTION},
            timeout=30.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            docs = data.get("documents")
            if isinstance(docs, list):
                return docs
            return data if isinstance(data, list) else []
        print(f"  Warning: GET /documents returned {resp.status_code}")
    except Exception as exc:
        print(f"  Warning: could not fetch documents — {exc}")
    return []


def patch_metadata(doc_id: str, patch: dict) -> bool:
    """PATCH directly to Supabase REST API."""
    if not _SB_URL or not _SB_KEY:
        return _patch_via_server(doc_id, patch)
    try:
        resp = httpx.patch(
            f"{_SB_URL}/rest/v1/Documents",
            headers=_SB_HEADERS,
            params={"doc_id": f"eq.{doc_id}", "collection": f"eq.{COLLECTION}"},
            json=patch,
            timeout=30.0,
        )
        return resp.status_code in (200, 204)
    except Exception:
        return False


def _patch_via_server(doc_id: str, patch: dict) -> bool:
    try:
        resp = httpx.patch(
            f"{SERVER_URL}/documents/{doc_id}",
            params={"collection": COLLECTION},
            json=patch,
            timeout=30.0,
        )
        return resp.status_code == 200
    except Exception:
        return False


def update_metadata_from_csv(docs: list) -> None:
    if not CSV_PATH.exists():
        print("No document_import.csv found — skipping metadata phase.")
        return

    with open(CSV_PATH, newline="", encoding="cp1252") as f:
        rows = list(csv.DictReader(f))

    print(f"{'='*60}")
    print(f"PHASE 2 — Updating metadata for {len(rows)} CSV rows")
    print(f"{'='*60}\n")

    matched, skipped, failed = 0, 0, 0

    for row in rows:
        title    = (row.get("title") or "").strip()
        author   = (row.get("author") or "").strip()
        abstract = (row.get("abstract") or "").strip()
        year     = (row.get("year") or "").strip()
        doi      = (row.get("doi") or "").strip()

        doc = _match_csv_to_doc(title, docs)
        if doc is None:
            print(f"  NO MATCH  {title[:70]}")
            skipped += 1
            continue

        doc_id = doc.get("doc_id") or doc.get("id") or ""
        if not doc_id:
            print(f"  NO DOC_ID {title[:70]}")
            skipped += 1
            continue

        patch: dict = {}
        if title:
            patch["title"] = title
        if author:
            patch["authors"] = author
        if abstract:
            patch["abstract"] = abstract
        if doi:
            patch["doi"] = doi
        if year:
            patch["year"] = int(year) if year.isdigit() else year

        if not patch:
            skipped += 1
            continue

        ok = patch_metadata(doc_id, patch)
        label = doc.get("filename", "")[:50]
        if ok:
            print(f"  UPDATED   {label}")
            matched += 1
        else:
            print(f"  FAILED    {label}")
            failed += 1

    print(f"\nPhase 2 done: {matched} updated, {skipped} unmatched, {failed} failed.\n")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    if not UPLOADS_DIR.exists():
        print(f"Uploads directory not found: {UPLOADS_DIR}")
        sys.exit(1)

    files = sorted(
        f for f in UPLOADS_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXT
    )

    if not files:
        print(f"No supported files found in {UPLOADS_DIR}")
        sys.exit(0)

    # Phase 1
    ingest_all(files)

    # Give the server a moment to finish writing Supabase records
    time.sleep(2)

    # Phase 2
    docs = fetch_documents()
    if not docs:
        print("Could not retrieve document list — skipping metadata update.")
        return

    print(f"Retrieved {len(docs)} documents from Supabase.\n")
    update_metadata_from_csv(docs)

    print("Sync complete.")


if __name__ == "__main__":
    main()
