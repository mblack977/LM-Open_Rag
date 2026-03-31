-- Retrieval Layer Schema Extension for Herb AI RAG System
-- This extends SUPABASE_MIGRATION.sql with retrieval evaluation and optimization tables

-- Create or replace the trigger function for auto-updating updated_at timestamp
-- (This may already exist from SUPABASE_MIGRATION.sql, but we include it here for standalone execution)
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

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

-- Benchmark Queries: Store evaluation queries with metadata
CREATE TABLE IF NOT EXISTS public."BenchmarkQueries" (
  id BIGSERIAL PRIMARY KEY,
  query_id TEXT NOT NULL UNIQUE,
  collection TEXT NOT NULL,
  query_text TEXT NOT NULL,
  
  -- Query classification
  query_type TEXT, -- e.g., 'definitional', 'empirical_evidence', 'critique', 'methodological', 'synthesis'
  section_goal TEXT, -- e.g., 'background', 'literature_review', 'methodology'
  difficulty TEXT, -- e.g., 'easy', 'medium', 'hard'
  
  -- Source of query
  source TEXT, -- e.g., 'user_interaction', 'hand_curated', 'section_heading'
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
  doc_relevance TEXT, -- 'highly_relevant', 'somewhat_relevant', 'not_relevant'
  
  -- Chunk-level relevance (more granular)
  chunk_id TEXT,
  chunk_index INTEGER,
  chunk_relevance TEXT, -- 'supporting_evidence', 'background_only', 'not_relevant'
  
  -- Evidence role labeling for synthesis
  evidence_role TEXT, -- 'definition', 'background', 'empirical_finding', 'critique', 'method', 'limitation', 'gap'
  
  -- Annotation metadata
  annotator TEXT,
  confidence REAL, -- 0.0 to 1.0
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
  mrr REAL, -- Mean Reciprocal Rank
  map_score REAL, -- Mean Average Precision
  
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
  optimization_type TEXT NOT NULL, -- 'grid_search', 'bayesian', 'per_query_type'
  
  -- Search space
  search_config JSONB,
  
  -- Best result
  best_run_id TEXT,
  best_profile_id BIGINT REFERENCES public."RetrievalProfiles"(id) ON DELETE SET NULL,
  best_metric_name TEXT, -- e.g., 'ndcg_at_10'
  best_metric_value REAL,
  baseline_metric_value REAL,
  improvement_pct REAL,
  
  -- All runs in this optimization
  run_ids JSONB,
  
  -- Metadata
  num_configurations_tested INTEGER,
  total_duration_seconds REAL,
  status TEXT, -- 'running', 'completed', 'failed'
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

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_retrieval_profiles_name ON public."RetrievalProfiles"(profile_name);
CREATE INDEX IF NOT EXISTS idx_retrieval_profiles_active ON public."RetrievalProfiles"(is_active) WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_project_retrieval_collection ON public."ProjectRetrievalSettings"(collection);

CREATE INDEX IF NOT EXISTS idx_benchmark_queries_collection ON public."BenchmarkQueries"(collection);
CREATE INDEX IF NOT EXISTS idx_benchmark_queries_type ON public."BenchmarkQueries"(query_type);
CREATE INDEX IF NOT EXISTS idx_benchmark_queries_active ON public."BenchmarkQueries"(is_active) WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_benchmark_labels_query ON public."BenchmarkRelevanceLabels"(query_id);
CREATE INDEX IF NOT EXISTS idx_benchmark_labels_doc ON public."BenchmarkRelevanceLabels"(doc_id);
CREATE INDEX IF NOT EXISTS idx_benchmark_labels_collection ON public."BenchmarkRelevanceLabels"(collection);

CREATE INDEX IF NOT EXISTS idx_retrieval_runs_collection ON public."RetrievalRuns"(collection);
CREATE INDEX IF NOT EXISTS idx_retrieval_runs_profile ON public."RetrievalRuns"(profile_id);

CREATE INDEX IF NOT EXISTS idx_retrieval_run_details_run ON public."RetrievalRunDetails"(run_id);
CREATE INDEX IF NOT EXISTS idx_retrieval_run_details_query ON public."RetrievalRunDetails"(query_id);

CREATE INDEX IF NOT EXISTS idx_optimization_history_collection ON public."OptimizationHistory"(collection);

-- Create triggers for updated_at
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

-- Insert default retrieval profiles
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

-- Grant permissions
GRANT ALL ON public."RetrievalProfiles" TO authenticated, service_role;
GRANT ALL ON public."ProjectRetrievalSettings" TO authenticated, service_role;
GRANT ALL ON public."BenchmarkQueries" TO authenticated, service_role;
GRANT ALL ON public."BenchmarkRelevanceLabels" TO authenticated, service_role;
GRANT ALL ON public."RetrievalRuns" TO authenticated, service_role;
GRANT ALL ON public."RetrievalRunDetails" TO authenticated, service_role;
GRANT ALL ON public."OptimizationHistory" TO authenticated, service_role;
GRANT ALL ON public."AnnotationSessions" TO authenticated, service_role;

-- Grant sequence permissions
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated, service_role;
