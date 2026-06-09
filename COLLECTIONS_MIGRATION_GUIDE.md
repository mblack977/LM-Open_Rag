# Collections Database Migration Guide

## Overview
Your collections system has been migrated from a **file-based system** to a **Supabase database-backed system**.

## What Changed

### Before (File-Based)
- Collections stored as folders in `data/collections/{collection_name}/`
- Metadata stored in `.collection.json` files
- No database table

### After (Database-Backed)
- Collections stored in Supabase `Collections` table
- Images stored in `data/collection_images/` directory
- Proper database relationships with Documents table

## Migration Steps

### 1. Run SQL Migration in Supabase

1. Open your Supabase project
2. Go to **SQL Editor**
3. Run the migration file: `CREATE_COLLECTIONS_TABLE.sql`

This will create:
- `Collections` table with columns: `id`, `name`, `display_name`, `description`, `image_url`, `created_at`, `updated_at`
- Indexes for faster lookups
- Foreign key columns in `Documents` and `DocumentChunks` tables (optional, for future use)

### 2. Restart Your Application

```powershell
# Stop the current server (Ctrl+C)
# Then restart
python main.py
```

### 3. Test Collection Creation

1. Open the dashboard at `http://localhost:8000/dashboard`
2. Click "Create Collection"
3. Fill in:
   - **Name**: e.g., "Research Papers"
   - **Description**: e.g., "Academic research papers on self-concept"
   - **Image** (optional): Upload a cover image
4. Click "Create Collection"
5. The collection should now appear as a card in the collections grid!

## Database Schema

### Collections Table

```sql
CREATE TABLE public."Collections" (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL UNIQUE,              -- Sanitized name (e.g., "research_papers")
  display_name TEXT NOT NULL,             -- Display name (e.g., "Research Papers")
  description TEXT,                        -- Collection description
  image_url TEXT,                          -- URL to collection image
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### How It Links to Documents

The `Documents` table has a `collection` field (TEXT) that references the `name` field in the `Collections` table.

Example:
- Collection: `name = "research_papers"`, `display_name = "Research Papers"`
- Document: `collection = "research_papers"`

## API Endpoints

### GET /collections
Returns all collections with metadata and document counts.

**Response:**
```json
{
  "status": "success",
  "collections": [
    {
      "name": "research_papers",
      "display_name": "Research Papers",
      "description": "Academic research papers",
      "image": "/collection-images/research_papers.jpg",
      "file_count": 5,
      "created_at": "2026-04-22T04:41:00Z",
      "has_metadata": true
    }
  ]
}
```

### POST /collections
Creates a new collection in the database.

**Form Data:**
- `name` (required): Collection name
- `description` (optional): Collection description
- `image` (optional): Cover image file

**Response:**
```json
{
  "status": "success",
  "collection": "research_papers",
  "metadata": {
    "id": "uuid-here",
    "name": "research_papers",
    "display_name": "Research Papers",
    "description": "Academic research papers",
    "image_url": "/collection-images/research_papers.jpg",
    "created_at": "2026-04-22T04:41:00Z"
  },
  "message": "Collection 'Research Papers' created successfully"
}
```

## Files Changed

1. **`CREATE_COLLECTIONS_TABLE.sql`** - SQL migration script
2. **`src/db_collection_manager.py`** - New database-backed collection manager
3. **`main.py`** - Updated to use `DBCollectionManager`
4. **`static/dashboard.js`** - Fixed to call the API endpoint

## Troubleshooting

### "Database collection manager not available"
- Check that Supabase environment variables are set in `.env`:
  - `SUPABASE_URL`
  - `SUPABASE_SERVICE_ROLE_KEY`
- Restart the application

### Collections not appearing
1. Check browser console for errors (F12)
2. Check server logs for errors
3. Verify the SQL migration ran successfully in Supabase
4. Try creating a test collection

### Image not displaying
- Images are stored in `data/collection_images/`
- Served at `/collection-images/{filename}`
- Check that the directory exists and has write permissions

## Backward Compatibility

The system still supports the old file-based collections as a fallback if Supabase is not available. However, new collections will only be created in the database.
