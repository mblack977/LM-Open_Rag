"""
Clean up herb_calibration collection from Supabase database
"""
import asyncio
import os
from dotenv import load_dotenv
from src.supabase_rest import SupabaseRestClient

async def clean_herb_calibration():
    load_dotenv()
    
    print("=" * 60)
    print("Cleaning herb_calibration collection from Supabase")
    print("=" * 60)
    
    client = SupabaseRestClient()
    
    # First, check how many records exist
    print("\nChecking current records...")
    
    try:
        chunks = await client.select(
            "DocumentChunks",
            select="id",
            filters={"collection": "eq.herb_calibration"}
        )
        print(f"  DocumentChunks: {len(chunks) if chunks else 0} records")
    except Exception as e:
        print(f"  DocumentChunks: Error - {e}")
        chunks = []
    
    try:
        docs = await client.select(
            "Documents",
            select="id",
            filters={"collection": "eq.herb_calibration"}
        )
        print(f"  Documents: {len(docs) if docs else 0} records")
    except Exception as e:
        print(f"  Documents: Error - {e}")
        docs = []
    
    # Delete chunks
    if chunks:
        print(f"\nDeleting {len(chunks)} chunks...")
        try:
            await client.delete(
                "DocumentChunks",
                filters={"collection": "eq.herb_calibration"}
            )
            print("  [OK] Chunks deleted")
        except Exception as e:
            print(f"  [ERROR] Error deleting chunks: {e}")
    
    # Delete documents
    if docs:
        print(f"\nDeleting {len(docs)} documents...")
        try:
            await client.delete(
                "Documents",
                filters={"collection": "eq.herb_calibration"}
            )
            print("  [OK] Documents deleted")
        except Exception as e:
            print(f"  [ERROR] Error deleting documents: {e}")
    
    # Verify deletion
    print("\nVerifying deletion...")
    try:
        chunks_after = await client.select(
            "DocumentChunks",
            select="id",
            filters={"collection": "eq.herb_calibration"}
        )
        docs_after = await client.select(
            "Documents",
            select="id",
            filters={"collection": "eq.herb_calibration"}
        )
        
        print(f"  DocumentChunks: {len(chunks_after) if chunks_after else 0} records remaining")
        print(f"  Documents: {len(docs_after) if docs_after else 0} records remaining")
        
        if (not chunks_after or len(chunks_after) == 0) and (not docs_after or len(docs_after) == 0):
            print("\n" + "=" * 60)
            print("[SUCCESS] CLEANUP COMPLETE")
            print("=" * 60)
            print("The herb_calibration collection is now empty.")
            print("You can now re-upload your documents.")
        else:
            print("\n[WARNING] Some records may still remain")
    except Exception as e:
        print(f"  Error verifying: {e}")

if __name__ == "__main__":
    asyncio.run(clean_herb_calibration())
