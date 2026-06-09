-- Create Collections Table in Supabase
-- Run this in Supabase Studio SQL Editor

-- Create Collections table
CREATE TABLE IF NOT EXISTS public."Collections" (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  description TEXT,
  image_url TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index on name for faster lookups
CREATE INDEX IF NOT EXISTS idx_collections_name ON public."Collections"(name);

-- Create trigger to auto-update updated_at timestamp
CREATE TRIGGER update_collections_updated_at
  BEFORE UPDATE ON public."Collections"
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions
GRANT ALL ON public."Collections" TO authenticated, service_role;

-- Add collection_id foreign key to Documents table (optional, for referential integrity)
-- This creates a proper relationship between Documents and Collections
ALTER TABLE public."Documents" 
  ADD COLUMN IF NOT EXISTS collection_id UUID REFERENCES public."Collections"(id) ON DELETE CASCADE;

-- Create index for the foreign key
CREATE INDEX IF NOT EXISTS idx_documents_collection_id ON public."Documents"(collection_id);

-- Add collection_id to DocumentChunks table as well
ALTER TABLE public."DocumentChunks"
  ADD COLUMN IF NOT EXISTS collection_id UUID REFERENCES public."Collections"(id) ON DELETE CASCADE;

-- Create index for the foreign key
CREATE INDEX IF NOT EXISTS idx_documentchunks_collection_id ON public."DocumentChunks"(collection_id);

-- Note: The existing 'collection' TEXT columns will remain for backward compatibility
-- New code should use collection_id, but we'll keep collection TEXT as a denormalized field
