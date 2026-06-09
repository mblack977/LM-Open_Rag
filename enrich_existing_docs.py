#!/usr/bin/env python3
"""
One-shot script: enrich all existing documents that have a DOI with CrossRef metadata.
Run from the project root:  python enrich_existing_docs.py
Optional flags:
  --collection <name>   limit to one collection
  --overwrite           overwrite fields that already have values
  --dry-run             preview CrossRef data without writing anything
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from src.supabase_rest import SupabaseRestClient, SupabaseRestError
from src.crossref_enricher import CrossRefEnricher


async def main(collection: str | None, overwrite: bool, dry_run: bool) -> None:
    try:
        supabase = SupabaseRestClient()
    except SupabaseRestError as e:
        print(f"Cannot connect to Supabase: {e}")
        sys.exit(1)

    mailto = os.getenv("CROSSREF_MAILTO", "")
    enricher = CrossRefEnricher(supabase, mailto)

    # Fetch all active documents that have a DOI entered
    filters: dict = {"is_active": "eq.true", "doi": "not.is.null"}
    if collection:
        filters["collection"] = f"eq.{collection}"

    rows = await supabase.select(
        "Documents",
        select="id,collection,title,doi,metadata_complete",
        filters=filters,
        limit=1000,
    )

    # Filter out rows where doi is an empty string (PostgREST not.is.null doesn't catch those)
    rows = [r for r in rows if (r.get("doi") or "").strip()]

    if not rows:
        print("No documents with a DOI found.")
        return

    print(f"Found {len(rows)} document(s) with a DOI.")
    if dry_run:
        print("DRY RUN — no data will be written.\n")
    print()

    counts = {"enriched": 0, "skipped": 0, "not_found": 0, "errors": 0}

    for i, doc in enumerate(rows, 1):
        doc_id = doc["id"]
        doi = doc.get("doi", "").strip()
        title = doc.get("title") or "(no title yet)"
        coll = doc.get("collection", "")
        prefix = f"[{i:>3}/{len(rows)}] id={doc_id} ({coll})"

        print(f"{prefix}")
        print(f"         DOI   : {doi}")
        print(f"         Title : {title}")

        try:
            if dry_run:
                result = await enricher.preview_document(doc_id)
                status = result.get("status")
                if status == "found":
                    data = result.get("crossref_data", {})
                    print(f"         Found : {data.get('title', '?')!r}")
                    print(f"         Author: {data.get('author', '?')}")
                    print(f"         Year  : {data.get('year', '?')}")
                else:
                    print(f"         Result: {status}")
            else:
                result = await enricher.enrich_document(doc_id, overwrite=overwrite)
                status = result.get("status", "error")
                bucket = status if status in counts else "errors"
                counts[bucket] += 1
                if status == "enriched":
                    updated = result.get("fields_updated", [])
                    score = result.get("match_score")
                    score_str = f"  score={score:.2f}" if score and score < 1.0 else ""
                    print(f"         OK    : updated {updated}{score_str}")
                elif status == "skipped":
                    print(f"         Skipped: {result.get('message', '')}")
                elif status == "not_found":
                    print(f"         Not found on CrossRef")
                else:
                    print(f"         ERROR : {result.get('message', status)}")
        except Exception as e:
            counts["errors"] += 1
            print(f"         ERROR : {e}")

        print()
        # Small pause — polite to CrossRef and avoids thundering herd
        await asyncio.sleep(0.15)

    if not dry_run:
        print("=" * 60)
        print(f"Complete.  enriched={counts['enriched']}  skipped={counts['skipped']}  "
              f"not_found={counts['not_found']}  errors={counts['errors']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enrich existing documents via CrossRef")
    parser.add_argument("--collection", default=None, help="Limit to one collection name")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing field values")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    asyncio.run(main(args.collection, args.overwrite, args.dry_run))
