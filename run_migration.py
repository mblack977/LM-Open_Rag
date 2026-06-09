import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import psycopg2
from psycopg2 import sql

def run_migration():
    """Run the COMPLETE_MIGRATION.sql file against the Supabase database."""
    
    # Load environment variables
    load_dotenv()
    
    # Get Supabase URL and parse connection details
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    if not supabase_url:
        print("ERROR: SUPABASE_URL not found in .env file")
        sys.exit(1)
    
    # Parse the Supabase URL to get the database connection string
    # For self-hosted Supabase, the Postgres is typically on port 5432
    # Format: postgresql://postgres:password@host:5432/postgres
    
    # Extract host from SUPABASE_URL (e.g., http://localhost:8000 -> localhost)
    host = supabase_url.replace('http://', '').replace('https://', '').split(':')[0]
    
    # Replace docker-internal hostname with localhost when running from host
    if host == 'host.docker.internal':
        host = 'localhost'
    
    # For self-hosted Supabase, get the password from environment
    # Check POSTGRES_PASSWORD first, then fall back to default
    db_password = os.getenv('POSTGRES_PASSWORD')
    
    if not db_password:
        print("\nWARNING: POSTGRES_PASSWORD not found in .env file")
        print("Please add POSTGRES_PASSWORD to your .env file")
        print("You can find this in: c:\\Herb Project\\supabase-selfhost\\docker\\.env")
        print("Look for the line: POSTGRES_PASSWORD=...")
        print("\nAlternatively, set it as an environment variable before running this script:")
        print("  set POSTGRES_PASSWORD=your-password")
        sys.exit(1)
    
    print(f"Connecting to Postgres at {host}:5432...")
    
    try:
        # Connect to the database
        # For Supabase, we need to connect to the 'postgres' database with specific settings
        conn = psycopg2.connect(
            host=host,
            port=5432,
            database='postgres',
            user='postgres',
            password=db_password,
            options='-c search_path=public'
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Read the migration file
        migration_file = Path(__file__).parent / 'COMPLETE_MIGRATION.sql'
        
        if not migration_file.exists():
            print(f"ERROR: Migration file not found at {migration_file}")
            sys.exit(1)
        
        print(f"Reading migration file: {migration_file}")
        with open(migration_file, 'r', encoding='utf-8') as f:
            migration_sql = f.read()
        
        # Execute the migration
        print("Executing migration...")
        cursor.execute(migration_sql)
        
        print("✓ Migration completed successfully!")
        
        # Verify tables were created
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('Documents', 'DocumentChunks', 'ChatSessions', 'ChatMessages')
            ORDER BY table_name;
        """)
        
        tables = cursor.fetchall()
        if tables:
            print("\nVerified tables:")
            for table in tables:
                print(f"  ✓ {table[0]}")
        
        cursor.close()
        conn.close()
        
    except psycopg2.Error as e:
        print(f"ERROR: Database error occurred:")
        print(f"  {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Unexpected error occurred:")
        print(f"  {e}")
        sys.exit(1)

if __name__ == '__main__':
    print("=" * 60)
    print("Herb AI RAG System - Database Migration")
    print("=" * 60)
    run_migration()
