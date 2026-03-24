-- Supabase Migration for Herb AI RAG System
-- Run this in Supabase Studio SQL Editor

-- Create Documents table
CREATE TABLE IF NOT EXISTS public."Documents" (
  id BIGSERIAL PRIMARY KEY,
  collection TEXT NOT NULL,
  doc_id TEXT NOT NULL,
  filename TEXT,
  file_path TEXT,
  file_size BIGINT,
  created_time TIMESTAMPTZ,
  modified_time TIMESTAMPTZ,
  title TEXT,
  authors TEXT,
  abstract TEXT,
  notes TEXT,
  tags JSONB DEFAULT '[]'::jsonb,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(collection, doc_id)
);

-- Create DocumentChunks table with tsvector for FTS
CREATE TABLE IF NOT EXISTS public."DocumentChunks" (
  id BIGSERIAL PRIMARY KEY,
  collection TEXT NOT NULL,
  doc_id TEXT NOT NULL,
  chunk_index INTEGER NOT NULL,
  chunk_text TEXT NOT NULL,
  title TEXT,
  authors TEXT,
  notes TEXT,
  tags JSONB DEFAULT '[]'::jsonb,
  search_vector tsvector GENERATED ALWAYS AS (
    setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(authors, '')), 'B') ||
    setweight(to_tsvector('english', coalesce(notes, '')), 'C') ||
    setweight(to_tsvector('english', coalesce(chunk_text, '')), 'D')
  ) STORED,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(collection, doc_id, chunk_index)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_documents_collection_docid ON public."Documents"(collection, doc_id);
CREATE INDEX IF NOT EXISTS idx_documentchunks_search_vector ON public."DocumentChunks" USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS idx_documentchunks_collection_docid ON public."DocumentChunks"(collection, doc_id);

-- Create trigger to auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_documents_updated_at
  BEFORE UPDATE ON public."Documents"
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_documentchunks_updated_at
  BEFORE UPDATE ON public."DocumentChunks"
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

-- Create FTS search function (BM25-like ranking)
CREATE OR REPLACE FUNCTION public.fts_search(
  p_collection TEXT,
  p_query TEXT,
  p_limit INTEGER DEFAULT 30
)
RETURNS TABLE(
  doc_id TEXT,
  chunk_index INTEGER,
  chunk_text TEXT,
  title TEXT,
  authors TEXT,
  notes TEXT,
  tags JSONB,
  rank REAL
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    dc.doc_id,
    dc.chunk_index,
    dc.chunk_text,
    dc.title,
    dc.authors,
    dc.notes,
    dc.tags,
    ts_rank(dc.search_vector, websearch_to_tsquery('english', p_query)) AS rank
  FROM public."DocumentChunks" dc
  WHERE dc.collection = p_collection
    AND dc.search_vector @@ websearch_to_tsquery('english', p_query)
  ORDER BY rank DESC
  LIMIT p_limit;
END;
$$ LANGUAGE plpgsql STABLE;

-- Grant permissions (adjust as needed for your Supabase setup)
GRANT ALL ON public."Documents" TO authenticated, service_role;
GRANT ALL ON public."DocumentChunks" TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.fts_search TO authenticated, service_role;
