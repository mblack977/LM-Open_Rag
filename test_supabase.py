"""
Quick test to verify Supabase connection and Collections table
"""
import asyncio
import os
from dotenv import load_dotenv
from src.supabase_rest import SupabaseRestClient

load_dotenv()

async def test_supabase():
    print("Testing Supabase connection...")
    print(f"SUPABASE_URL: {os.getenv('SUPABASE_URL')}")
    print(f"SUPABASE_SERVICE_ROLE_KEY: {'***' if os.getenv('SUPABASE_SERVICE_ROLE_KEY') else 'NOT SET'}")
    
    try:
        client = SupabaseRestClient()
        print("✓ Supabase client initialized")
        
        # Try to query Collections table
        print("\nTesting Collections table...")
        collections = await client.select("Collections", select="*")
        print(f"✓ Collections table exists! Found {len(collections)} collections")
        
        for coll in collections:
            print(f"  - {coll.get('display_name')} ({coll.get('name')})")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {type(e).__name__}: {str(e)}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_supabase())
    
    if not success:
        print("\n" + "="*60)
        print("TROUBLESHOOTING:")
        print("="*60)
        print("1. Check your .env file has SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
        print("2. Run the SQL migration: CREATE_COLLECTIONS_TABLE.sql in Supabase Studio")
        print("3. Verify the Collections table exists in Supabase")
        print("="*60)
