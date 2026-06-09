"""
dedup_collection.py — Remove duplicate Supabase document records for a collection.

Keeps the most recently created record for each unique filename and deletes the
rest via the HerbGPT /documents/{doc_id} API (which also cleans Qdrant vectors
and DocumentChunks).

Usage:
    python dedup_collection.py [collection]
    python dedup_collection.py herbgpt        # default

Use --dry-run to preview without deleting:
    python dedup_collection.py herbgpt --dry-run
"""

import sys
import time
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")

import httpx

COLLECTION = next((a for a in sys.argv[1:] if not a.startswith("--")), "herbgpt")
DRY_RUN    = "--dry-run" in sys.argv
SERVER_URL = "http://localhost:8010"


def fetch_all_documents() -> list:
    resp = httpx.get(
        f"{SERVER_URL}/documents",
        params={"collection": COLLECTION},
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json()
    docs = data.get("documents")
    if isinstance(docs, list):
        return docs
    return data if isinstance(data, list) else []


def delete_document(doc_id: str) -> bool:
    resp = httpx.delete(
        f"{SERVER_URL}/documents/{doc_id}",
        params={"collection": COLLECTION},
        timeout=30.0,
    )
    return resp.status_code == 200


def main():
    print(f"Collection : {COLLECTION}")
    print(f"Mode       : {'DRY RUN (no deletions)' if DRY_RUN else 'LIVE'}\n")

    docs = fetch_all_documents()
    print(f"Total records fetched: {len(docs)}\n")

    # Group by filename, sort each group newest-first (by created_at or id)
    by_filename: dict[str, list] = defaultdict(list)
    for doc in docs:
        fname = (doc.get("filename") or "").strip()
        if not fname:
            fname = f"__no_filename_{doc.get('doc_id', doc.get('id', 'unknown'))}__"
        by_filename[fname].append(doc)

    dupes_found = 0
    to_delete: list[tuple[str, str]] = []  # (doc_id, filename)

    for fname, group in sorted(by_filename.items()):
        if len(group) <= 1:
            continue
        # Sort: prefer complete+active, then newest created_at
        def sort_key(d):
            is_complete = 1 if d.get("ingestion_status") == "complete" else 0
            is_active   = 1 if d.get("is_active", True) else 0
            created     = d.get("created_at") or ""
            return (is_complete, is_active, created)

        group.sort(key=sort_key, reverse=True)
        keep = group[0]
        dupes = group[1:]
        dupes_found += len(dupes)

        print(f"  KEEP  [{keep.get('doc_id','?')[:12]}] {fname[:60]}")
        for d in dupes:
            status = d.get("ingestion_status", "?")
            print(f"  DEL   [{d.get('doc_id','?')[:12]}] {fname[:60]}  ({status})")
            to_delete.append((d.get("doc_id", ""), fname))

    print(f"\nUnique filenames : {len(by_filename)}")
    print(f"Duplicate records: {dupes_found}")

    if dupes_found == 0:
        print("\nNo duplicates found — nothing to do.")
        return

    if DRY_RUN:
        print("\nDry run — no records deleted.")
        return

    print(f"\nDeleting {len(to_delete)} duplicate records...")
    deleted, failed = 0, 0
    for doc_id, fname in to_delete:
        if not doc_id:
            print(f"  SKIP  (no doc_id) {fname[:60]}")
            failed += 1
            continue
        ok = delete_document(doc_id)
        if ok:
            print(f"  DELETED  {doc_id[:12]}  {fname[:50]}")
            deleted += 1
        else:
            print(f"  FAILED   {doc_id[:12]}  {fname[:50]}")
            failed += 1
        time.sleep(0.1)

    print(f"\nDone: {deleted} deleted, {failed} failed.")


if __name__ == "__main__":
    main()
