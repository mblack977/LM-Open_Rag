-- Complete Migration for Herb AI RAG System
-- This file consolidates SUPABASE_MIGRATION.sql and RETRIEVAL_SCHEMA.sql
-- Run this once to set up a complete copy of the herbgpt database

-- ============================================================================
-- CORE TABLES: Documents and DocumentChunks
-- ============================================================================

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

-- ============================================================================
-- RETRIEVAL PROFILES AND PROJECT SETTINGS
-- ============================================================================

-- Retrieval Profiles: Store predefined and custom retrieval configurations
CREATE TABLE IF NOT EXISTS public."RetrievalProfiles" (
  id BIGSERIAL PRIMARY KEY,
  profile_name TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  description TEXT,
  is_system BOOLEAN DEFAULT FALSE,
  is_active BOOLEAN DEFAULT TRUE,
  
  -- Retrieval method weights (sum should be 1.0 for normalized profiles)
  bm25_weight REAL DEFAULT 0.0,
  pg_fts_weight REAL DEFAULT 0.0,
  pg_vec_weight REAL DEFAULT 0.0,
  
  -- Retrieval settings
  use_reranker BOOLEAN DEFAULT FALSE,
  reranker_model TEXT,
  normalize_scores BOOLEAN DEFAULT TRUE,
  metadata_boost REAL DEFAULT 0.0,
  citation_graph_boost REAL DEFAULT 0.0,
  
  -- Retrieval limits
  top_k INTEGER DEFAULT 10,
  bm25_limit INTEGER DEFAULT 30,
  fts_limit INTEGER DEFAULT 30,
  vec_limit INTEGER DEFAULT 30,
  
  -- Metadata
  created_by TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  CONSTRAINT valid_weights CHECK (
    bm25_weight >= 0 AND bm25_weight <= 1 AND
    pg_fts_weight >= 0 AND pg_fts_weight <= 1 AND
    pg_vec_weight >= 0 AND pg_vec_weight <= 1
  )
);

-- Project Retrieval Settings: Map projects/collections to retrieval profiles
CREATE TABLE IF NOT EXISTS public."ProjectRetrievalSettings" (
  id BIGSERIAL PRIMARY KEY,
  collection TEXT NOT NULL UNIQUE,
  profile_id BIGINT REFERENCES public."RetrievalProfiles"(id) ON DELETE SET NULL,
  profile_name TEXT,
  
  -- Override settings (if not using a profile)
  custom_bm25_weight REAL,
  custom_pg_fts_weight REAL,
  custom_pg_vec_weight REAL,
  custom_use_reranker BOOLEAN,
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- BENCHMARK AND EVALUATION TABLES
-- ============================================================================

-- Benchmark Queries: Store evaluation queries with metadata
CREATE TABLE IF NOT EXISTS public."BenchmarkQueries" (
  id BIGSERIAL PRIMARY KEY,
  query_id TEXT NOT NULL UNIQUE,
  collection TEXT NOT NULL,
  query_text TEXT NOT NULL,
  
  -- Query classification
  query_type TEXT,
  section_goal TEXT,
  difficulty TEXT,
  
  -- Source of query
  source TEXT,
  source_metadata JSONB,
  
  notes TEXT,
  is_active BOOLEAN DEFAULT TRUE,
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  CONSTRAINT unique_query_per_collection UNIQUE(collection, query_id)
);

-- Benchmark Relevance Labels: Ground truth for what documents/chunks are relevant
CREATE TABLE IF NOT EXISTS public."BenchmarkRelevanceLabels" (
  id BIGSERIAL PRIMARY KEY,
  query_id TEXT NOT NULL,
  collection TEXT NOT NULL,
  
  -- Document-level relevance
  doc_id TEXT,
  doc_relevance TEXT,
  
  -- Chunk-level relevance (more granular)
  chunk_id TEXT,
  chunk_index INTEGER,
  chunk_relevance TEXT,
  
  -- Evidence role labeling for synthesis
  evidence_role TEXT,
  
  -- Annotation metadata
  annotator TEXT,
  confidence REAL,
  notes TEXT,
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  FOREIGN KEY (query_id) REFERENCES public."BenchmarkQueries"(query_id) ON DELETE CASCADE,
  
  CONSTRAINT valid_confidence CHECK (confidence >= 0 AND confidence <= 1),
  CONSTRAINT has_doc_or_chunk CHECK (doc_id IS NOT NULL OR chunk_id IS NOT NULL)
);

-- Retrieval Runs: Store results of retrieval evaluations
CREATE TABLE IF NOT EXISTS public."RetrievalRuns" (
  id BIGSERIAL PRIMARY KEY,
  run_id TEXT NOT NULL UNIQUE,
  run_name TEXT,
  collection TEXT NOT NULL,
  
  -- Profile used for this run
  profile_id BIGINT REFERENCES public."RetrievalProfiles"(id) ON DELETE SET NULL,
  profile_name TEXT,
  
  -- Retrieval configuration snapshot
  bm25_weight REAL,
  pg_fts_weight REAL,
  pg_vec_weight REAL,
  use_reranker BOOLEAN,
  reranker_model TEXT,
  normalize_scores BOOLEAN,
  top_k INTEGER,
  
  -- Evaluation metrics
  precision_at_5 REAL,
  precision_at_10 REAL,
  recall_at_5 REAL,
  recall_at_10 REAL,
  recall_at_20 REAL,
  ndcg_at_5 REAL,
  ndcg_at_10 REAL,
  mrr REAL,
  map_score REAL,
  
  -- Query type breakdown (JSONB for flexibility)
  metrics_by_query_type JSONB,
  
  -- Run metadata
  num_queries INTEGER,
  avg_retrieval_time_ms REAL,
  benchmark_set_id TEXT,
  notes TEXT,
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  
  CONSTRAINT valid_metrics CHECK (
    (precision_at_5 IS NULL OR (precision_at_5 >= 0 AND precision_at_5 <= 1)) AND
    (recall_at_10 IS NULL OR (recall_at_10 >= 0 AND recall_at_10 <= 1)) AND
    (ndcg_at_10 IS NULL OR (ndcg_at_10 >= 0 AND ndcg_at_10 <= 1))
  )
);

-- Retrieval Run Details: Per-query results for a run
CREATE TABLE IF NOT EXISTS public."RetrievalRunDetails" (
  id BIGSERIAL PRIMARY KEY,
  run_id TEXT NOT NULL,
  query_id TEXT NOT NULL,
  
  -- Retrieved results (top-k doc/chunk IDs in order)
  retrieved_doc_ids JSONB,
  retrieved_chunk_ids JSONB,
  retrieved_scores JSONB,
  
  -- Per-query metrics
  precision_at_5 REAL,
  recall_at_10 REAL,
  ndcg_at_10 REAL,
  reciprocal_rank REAL,
  
  retrieval_time_ms REAL,
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  
  FOREIGN KEY (run_id) REFERENCES public."RetrievalRuns"(run_id) ON DELETE CASCADE,
  FOREIGN KEY (query_id) REFERENCES public."BenchmarkQueries"(query_id) ON DELETE CASCADE
);

-- Optimization History: Track grid search and optimization results
CREATE TABLE IF NOT EXISTS public."OptimizationHistory" (
  id BIGSERIAL PRIMARY KEY,
  optimization_id TEXT NOT NULL UNIQUE,
  collection TEXT NOT NULL,
  optimization_type TEXT NOT NULL,
  
  -- Search space
  search_config JSONB,
  
  -- Best result
  best_run_id TEXT,
  best_profile_id BIGINT REFERENCES public."RetrievalProfiles"(id) ON DELETE SET NULL,
  best_metric_name TEXT,
  best_metric_value REAL,
  baseline_metric_value REAL,
  improvement_pct REAL,
  
  -- All runs in this optimization
  run_ids JSONB,
  
  -- Metadata
  num_configurations_tested INTEGER,
  total_duration_seconds REAL,
  status TEXT,
  notes TEXT,
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ,
  
  FOREIGN KEY (best_run_id) REFERENCES public."RetrievalRuns"(run_id) ON DELETE SET NULL
);

-- Annotation Sessions: Track annotation work
CREATE TABLE IF NOT EXISTS public."AnnotationSessions" (
  id BIGSERIAL PRIMARY KEY,
  session_id TEXT NOT NULL UNIQUE,
  collection TEXT NOT NULL,
  annotator TEXT NOT NULL,
  
  queries_annotated INTEGER DEFAULT 0,
  labels_created INTEGER DEFAULT 0,
  
  started_at TIMESTAMPTZ DEFAULT NOW(),
  last_activity_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Core table indexes
CREATE INDEX IF NOT EXISTS idx_documents_collection_docid ON public."Documents"(collection, doc_id);
CREATE INDEX IF NOT EXISTS idx_documentchunks_search_vector ON public."DocumentChunks" USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS idx_documentchunks_collection_docid ON public."DocumentChunks"(collection, doc_id);

-- Retrieval profile indexes
CREATE INDEX IF NOT EXISTS idx_retrieval_profiles_name ON public."RetrievalProfiles"(profile_name);
CREATE INDEX IF NOT EXISTS idx_retrieval_profiles_active ON public."RetrievalProfiles"(is_active) WHERE is_active = TRUE;

-- Project settings indexes
CREATE INDEX IF NOT EXISTS idx_project_retrieval_collection ON public."ProjectRetrievalSettings"(collection);

-- Benchmark indexes
CREATE INDEX IF NOT EXISTS idx_benchmark_queries_collection ON public."BenchmarkQueries"(collection);
CREATE INDEX IF NOT EXISTS idx_benchmark_queries_type ON public."BenchmarkQueries"(query_type);
CREATE INDEX IF NOT EXISTS idx_benchmark_queries_active ON public."BenchmarkQueries"(is_active) WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_benchmark_labels_query ON public."BenchmarkRelevanceLabels"(query_id);
CREATE INDEX IF NOT EXISTS idx_benchmark_labels_doc ON public."BenchmarkRelevanceLabels"(doc_id);
CREATE INDEX IF NOT EXISTS idx_benchmark_labels_collection ON public."BenchmarkRelevanceLabels"(collection);

-- Retrieval run indexes
CREATE INDEX IF NOT EXISTS idx_retrieval_runs_collection ON public."RetrievalRuns"(collection);
CREATE INDEX IF NOT EXISTS idx_retrieval_runs_profile ON public."RetrievalRuns"(profile_id);

CREATE INDEX IF NOT EXISTS idx_retrieval_run_details_run ON public."RetrievalRunDetails"(run_id);
CREATE INDEX IF NOT EXISTS idx_retrieval_run_details_query ON public."RetrievalRunDetails"(query_id);

-- Optimization indexes
CREATE INDEX IF NOT EXISTS idx_optimization_history_collection ON public."OptimizationHistory"(collection);

-- ============================================================================
-- FUNCTIONS AND TRIGGERS
-- ============================================================================

-- Create trigger function for auto-updating updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply triggers to all tables with updated_at
CREATE TRIGGER update_documents_updated_at
  BEFORE UPDATE ON public."Documents"
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_documentchunks_updated_at
  BEFORE UPDATE ON public."DocumentChunks"
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_retrieval_profiles_updated_at
  BEFORE UPDATE ON public."RetrievalProfiles"
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_project_retrieval_settings_updated_at
  BEFORE UPDATE ON public."ProjectRetrievalSettings"
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_benchmark_queries_updated_at
  BEFORE UPDATE ON public."BenchmarkQueries"
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_benchmark_labels_updated_at
  BEFORE UPDATE ON public."BenchmarkRelevanceLabels"
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

-- ============================================================================
-- DEFAULT DATA: Insert default retrieval profiles
-- ============================================================================

INSERT INTO public."RetrievalProfiles" (
  profile_name, display_name, description, is_system,
  bm25_weight, pg_fts_weight, pg_vec_weight,
  use_reranker, normalize_scores, top_k
) VALUES
  (
    'keyword_heavy',
    'Keyword Heavy',
    'Prioritizes exact keyword matching. Best for queries with specific terminology or technical terms.',
    TRUE,
    0.50, 0.30, 0.20,
    FALSE, TRUE, 10
  ),
  (
    'balanced',
    'Balanced',
    'Balanced approach combining keyword matching and semantic understanding. Good general-purpose profile.',
    TRUE,
    0.30, 0.20, 0.50,
    FALSE, TRUE, 10
  ),
  (
    'conceptual',
    'Conceptual',
    'Emphasizes semantic similarity. Best for conceptual queries and finding related ideas.',
    TRUE,
    0.10, 0.10, 0.80,
    FALSE, TRUE, 10
  ),
  (
    'academic_evidence',
    'Academic Evidence',
    'Optimized for finding empirical evidence and research findings. Balanced with slight semantic preference.',
    TRUE,
    0.25, 0.25, 0.50,
    FALSE, TRUE, 10
  ),
  (
    'custom',
    'Custom',
    'User-defined custom profile. Tune weights manually in advanced settings.',
    FALSE,
    0.33, 0.33, 0.34,
    FALSE, TRUE, 10
  )
ON CONFLICT (profile_name) DO NOTHING;

-- ============================================================================
-- PERMISSIONS
-- ============================================================================

-- Grant permissions on tables
GRANT ALL ON public."Documents" TO authenticated, service_role;
GRANT ALL ON public."DocumentChunks" TO authenticated, service_role;
GRANT ALL ON public."RetrievalProfiles" TO authenticated, service_role;
GRANT ALL ON public."ProjectRetrievalSettings" TO authenticated, service_role;
GRANT ALL ON public."BenchmarkQueries" TO authenticated, service_role;
GRANT ALL ON public."BenchmarkRelevanceLabels" TO authenticated, service_role;
GRANT ALL ON public."RetrievalRuns" TO authenticated, service_role;
GRANT ALL ON public."RetrievalRunDetails" TO authenticated, service_role;
GRANT ALL ON public."OptimizationHistory" TO authenticated, service_role;
GRANT ALL ON public."AnnotationSessions" TO authenticated, service_role;

-- Grant function permissions
GRANT EXECUTE ON FUNCTION public.fts_search TO authenticated, service_role;

-- Grant sequence permissions
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated, service_role;

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================
-- This migration creates all tables, indexes, functions, and default data
-- needed for the Herb AI RAG system with retrieval evaluation capabilities.
