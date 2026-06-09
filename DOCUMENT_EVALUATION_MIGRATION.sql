-- ============================================================================
-- DOCUMENT OPERATIONS & EVALUATION LAYERS MIGRATION
-- ============================================================================
-- This migration extends the existing schema to support:
-- 1. Enhanced document lifecycle management
-- 2. Query run tracking and evaluation
-- 3. Document performance analytics
--
-- Run this after COMPLETE_MIGRATION.sql
-- ============================================================================

-- ============================================================================
-- PHASE 1: EXTEND DOCUMENTS TABLE
-- ============================================================================

-- Add document lifecycle and tracking fields to existing Documents table
DO $$ 
BEGIN
    -- Document classification
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='Documents' AND column_name='document_type') THEN
        ALTER TABLE public."Documents" ADD COLUMN document_type TEXT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='Documents' AND column_name='author') THEN
        ALTER TABLE public."Documents" ADD COLUMN author TEXT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='Documents' AND column_name='year') THEN
        ALTER TABLE public."Documents" ADD COLUMN year INTEGER;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='Documents' AND column_name='doi') THEN
        ALTER TABLE public."Documents" ADD COLUMN doi TEXT;
    END IF;
    
    -- Source and workflow tracking
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='Documents' AND column_name='source_type') THEN
        ALTER TABLE public."Documents" ADD COLUMN source_type TEXT DEFAULT 'uploaded';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='Documents' AND column_name='pdf_attached') THEN
        ALTER TABLE public."Documents" ADD COLUMN pdf_attached BOOLEAN DEFAULT FALSE;
    END IF;
    
    -- Ingestion tracking
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='Documents' AND column_name='ingestion_status') THEN
        ALTER TABLE public."Documents" ADD COLUMN ingestion_status TEXT DEFAULT 'not_uploaded';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='Documents' AND column_name='ingested_at') THEN
        ALTER TABLE public."Documents" ADD COLUMN ingested_at TIMESTAMPTZ;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='Documents' AND column_name='chunk_count') THEN
        ALTER TABLE public."Documents" ADD COLUMN chunk_count INTEGER DEFAULT 0;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='Documents' AND column_name='embedding_model') THEN
        ALTER TABLE public."Documents" ADD COLUMN embedding_model TEXT;
    END IF;
    
    -- Quality and status flags
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='Documents' AND column_name='metadata_complete') THEN
        ALTER TABLE public."Documents" ADD COLUMN metadata_complete BOOLEAN DEFAULT FALSE;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='Documents' AND column_name='processing_error') THEN
        ALTER TABLE public."Documents" ADD COLUMN processing_error TEXT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='Documents' AND column_name='needs_review') THEN
        ALTER TABLE public."Documents" ADD COLUMN needs_review BOOLEAN DEFAULT FALSE;
    END IF;
    
    -- Usage statistics
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='Documents' AND column_name='last_queried_at') THEN
        ALTER TABLE public."Documents" ADD COLUMN last_queried_at TIMESTAMPTZ;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='Documents' AND column_name='times_retrieved') THEN
        ALTER TABLE public."Documents" ADD COLUMN times_retrieved INTEGER DEFAULT 0;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='Documents' AND column_name='times_cited') THEN
        ALTER TABLE public."Documents" ADD COLUMN times_cited INTEGER DEFAULT 0;
    END IF;
    
    -- Active status
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='Documents' AND column_name='is_active') THEN
        ALTER TABLE public."Documents" ADD COLUMN is_active BOOLEAN DEFAULT TRUE;
    END IF;
    
    -- Project grouping
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='Documents' AND column_name='project_id') THEN
        ALTER TABLE public."Documents" ADD COLUMN project_id UUID;
    END IF;
    
    -- User ownership
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='Documents' AND column_name='user_id') THEN
        ALTER TABLE public."Documents" ADD COLUMN user_id TEXT DEFAULT 'default_user';
    END IF;
END $$;

-- Update existing documents to have pdf_attached = true if they have a file_path
UPDATE public."Documents" 
SET pdf_attached = TRUE 
WHERE file_path IS NOT NULL AND file_path != '';

-- Update existing documents to have ingestion_status = 'complete' if they have chunks
UPDATE public."Documents" d
SET ingestion_status = 'complete',
    chunk_count = (
        SELECT COUNT(*) 
        FROM public."DocumentChunks" dc 
        WHERE dc.collection = d.collection AND dc.doc_id = d.doc_id
    )
WHERE EXISTS (
    SELECT 1 FROM public."DocumentChunks" dc 
    WHERE dc.collection = d.collection AND dc.doc_id = d.doc_id
);

-- Create indexes for new fields
CREATE INDEX IF NOT EXISTS idx_documents_ingestion_status ON public."Documents"(ingestion_status);
CREATE INDEX IF NOT EXISTS idx_documents_pdf_attached ON public."Documents"(pdf_attached);
CREATE INDEX IF NOT EXISTS idx_documents_document_type ON public."Documents"(document_type);
CREATE INDEX IF NOT EXISTS idx_documents_user_id ON public."Documents"(user_id);
CREATE INDEX IF NOT EXISTS idx_documents_project_id ON public."Documents"(project_id);
CREATE INDEX IF NOT EXISTS idx_documents_is_active ON public."Documents"(is_active) WHERE is_active = TRUE;

-- ============================================================================
-- PHASE 2: CREATE PROJECTS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS public."Projects" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT DEFAULT 'default_user',
    name TEXT NOT NULL,
    description TEXT,
    collection TEXT UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_projects_user_id ON public."Projects"(user_id);
CREATE INDEX IF NOT EXISTS idx_projects_collection ON public."Projects"(collection);

-- Add foreign key constraint for Documents.project_id
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'documents_project_id_fkey'
    ) THEN
        ALTER TABLE public."Documents" 
        ADD CONSTRAINT documents_project_id_fkey 
        FOREIGN KEY (project_id) REFERENCES public."Projects"(id) ON DELETE SET NULL;
    END IF;
END $$;

-- ============================================================================
-- PHASE 3: CREATE DOCUMENT INGESTION JOBS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS public."DocumentIngestionJobs" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id BIGINT REFERENCES public."Documents"(id) ON DELETE CASCADE,
    collection TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued', 'processing', 'complete', 'failed')),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    parser_used TEXT,
    chunking_method TEXT,
    chunk_size INTEGER,
    chunk_overlap INTEGER,
    embedding_model TEXT,
    chunks_created INTEGER DEFAULT 0,
    error_message TEXT,
    triggered_by TEXT DEFAULT 'user',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_document ON public."DocumentIngestionJobs"(document_id);
CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_status ON public."DocumentIngestionJobs"(status);
CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_collection ON public."DocumentIngestionJobs"(collection);
CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_created ON public."DocumentIngestionJobs"(created_at DESC);

-- ============================================================================
-- PHASE 4: CREATE QUERY RUNS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS public."QueryRuns" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT DEFAULT 'default_user',
    project_id UUID REFERENCES public."Projects"(id) ON DELETE SET NULL,
    session_id UUID REFERENCES public."ChatSessions"(id) ON DELETE SET NULL,
    message_id UUID REFERENCES public."ChatMessages"(id) ON DELETE SET NULL,
    
    -- Query details
    user_query TEXT NOT NULL,
    final_response TEXT,
    collection TEXT NOT NULL,
    
    -- Retrieval configuration
    retrieval_mode TEXT,
    retrieval_profile TEXT,
    top_k INTEGER,
    top_k_sent_to_llm INTEGER,
    reranker_used BOOLEAN DEFAULT FALSE,
    reranker_model TEXT,
    
    -- LLM configuration
    llm_model TEXT,
    embedding_model TEXT,
    temperature REAL,
    prompt_template_version TEXT,
    system_prompt_version TEXT,
    
    -- Performance metrics
    response_time_ms REAL,
    retrieval_time_ms REAL,
    llm_time_ms REAL,
    token_input INTEGER,
    token_output INTEGER,
    estimated_cost REAL,
    
    -- Metadata
    use_case_type TEXT,
    metadata_filters_used JSONB,
    run_config_json JSONB,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_query_runs_session ON public."QueryRuns"(session_id);
CREATE INDEX IF NOT EXISTS idx_query_runs_message ON public."QueryRuns"(message_id);
CREATE INDEX IF NOT EXISTS idx_query_runs_collection ON public."QueryRuns"(collection);
CREATE INDEX IF NOT EXISTS idx_query_runs_created ON public."QueryRuns"(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_query_runs_use_case ON public."QueryRuns"(use_case_type);
CREATE INDEX IF NOT EXISTS idx_query_runs_user ON public."QueryRuns"(user_id);
CREATE INDEX IF NOT EXISTS idx_query_runs_project ON public."QueryRuns"(project_id);

-- ============================================================================
-- PHASE 5: CREATE QUERY RUN DOCUMENTS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS public."QueryRunDocuments" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_run_id UUID REFERENCES public."QueryRuns"(id) ON DELETE CASCADE,
    document_id BIGINT REFERENCES public."Documents"(id) ON DELETE CASCADE,
    chunk_id BIGINT REFERENCES public."DocumentChunks"(id) ON DELETE CASCADE,
    
    -- Retrieval details
    retrieval_rank INTEGER,
    retrieval_score REAL,
    retrieval_source TEXT,
    rerank_score REAL,
    
    -- Usage flags
    was_retrieved BOOLEAN DEFAULT TRUE,
    was_in_context BOOLEAN DEFAULT FALSE,
    was_cited BOOLEAN DEFAULT FALSE,
    
    contribution_type TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_query_run_docs_run ON public."QueryRunDocuments"(query_run_id);
CREATE INDEX IF NOT EXISTS idx_query_run_docs_document ON public."QueryRunDocuments"(document_id);
CREATE INDEX IF NOT EXISTS idx_query_run_docs_chunk ON public."QueryRunDocuments"(chunk_id);
CREATE INDEX IF NOT EXISTS idx_query_run_docs_retrieved ON public."QueryRunDocuments"(was_retrieved) WHERE was_retrieved = TRUE;
CREATE INDEX IF NOT EXISTS idx_query_run_docs_cited ON public."QueryRunDocuments"(was_cited) WHERE was_cited = TRUE;

-- ============================================================================
-- PHASE 6: CREATE QUERY RUN EVALUATIONS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS public."QueryRunEvaluations" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_run_id UUID REFERENCES public."QueryRuns"(id) ON DELETE CASCADE,
    evaluator_user_id TEXT DEFAULT 'default_user',
    
    -- Quality scores (1-5 scale)
    overall_score INTEGER CHECK (overall_score >= 1 AND overall_score <= 5),
    accuracy_score INTEGER CHECK (accuracy_score >= 1 AND accuracy_score <= 5),
    relevance_score INTEGER CHECK (relevance_score >= 1 AND relevance_score <= 5),
    completeness_score INTEGER CHECK (completeness_score >= 1 AND completeness_score <= 5),
    clarity_score INTEGER CHECK (clarity_score >= 1 AND clarity_score <= 5),
    source_usefulness_score INTEGER CHECK (source_usefulness_score >= 1 AND source_usefulness_score <= 5),
    citation_quality_score INTEGER CHECK (citation_quality_score >= 1 AND citation_quality_score <= 5),
    
    -- Binary flags
    hallucination_flag BOOLEAN DEFAULT FALSE,
    response_preference TEXT CHECK (response_preference IN ('preferred', 'not_preferred', 'neutral')),
    
    -- Feedback
    feedback_text TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_query_evals_run ON public."QueryRunEvaluations"(query_run_id);
CREATE INDEX IF NOT EXISTS idx_query_evals_overall ON public."QueryRunEvaluations"(overall_score);
CREATE INDEX IF NOT EXISTS idx_query_evals_evaluator ON public."QueryRunEvaluations"(evaluator_user_id);
CREATE INDEX IF NOT EXISTS idx_query_evals_created ON public."QueryRunEvaluations"(created_at DESC);

-- ============================================================================
-- PHASE 7: CREATE DOCUMENT PERFORMANCE SUMMARY VIEW
-- ============================================================================

-- Drop existing view if it exists
DROP MATERIALIZED VIEW IF EXISTS public."DocumentPerformanceSummary" CASCADE;

CREATE MATERIALIZED VIEW public."DocumentPerformanceSummary" AS
SELECT 
    d.id,
    d.collection,
    d.doc_id,
    d.title,
    d.filename,
    d.document_type,
    d.author,
    d.year,
    d.ingestion_status,
    d.pdf_attached,
    d.metadata_complete,
    d.project_id,
    d.user_id,
    d.is_active,
    
    -- Retrieval stats
    COALESCE(COUNT(DISTINCT qrd.query_run_id) FILTER (WHERE qrd.was_retrieved), 0) as total_retrievals,
    COALESCE(COUNT(DISTINCT qrd.query_run_id) FILTER (WHERE qrd.was_in_context), 0) as total_in_context,
    COALESCE(COUNT(DISTINCT qrd.query_run_id) FILTER (WHERE qrd.was_cited), 0) as total_citations,
    
    -- Quality metrics
    AVG(qre.overall_score) as avg_overall_score,
    AVG(qre.accuracy_score) as avg_accuracy_score,
    AVG(qre.relevance_score) as avg_relevance_score,
    AVG(qre.source_usefulness_score) as avg_source_usefulness_score,
    
    -- Timestamps
    MAX(qr.created_at) as last_used_at,
    d.created_at,
    d.updated_at
    
FROM public."Documents" d
LEFT JOIN public."QueryRunDocuments" qrd ON d.id = qrd.document_id
LEFT JOIN public."QueryRuns" qr ON qrd.query_run_id = qr.id
LEFT JOIN public."QueryRunEvaluations" qre ON qr.id = qre.query_run_id
GROUP BY d.id;

CREATE UNIQUE INDEX idx_doc_perf_summary_id ON public."DocumentPerformanceSummary"(id);
CREATE INDEX idx_doc_perf_summary_collection ON public."DocumentPerformanceSummary"(collection);
CREATE INDEX idx_doc_perf_summary_status ON public."DocumentPerformanceSummary"(ingestion_status);
CREATE INDEX idx_doc_perf_summary_retrievals ON public."DocumentPerformanceSummary"(total_retrievals DESC);
CREATE INDEX idx_doc_perf_summary_citations ON public."DocumentPerformanceSummary"(total_citations DESC);

-- ============================================================================
-- PHASE 8: CREATE HELPER FUNCTIONS
-- ============================================================================

-- Function to refresh the materialized view
CREATE OR REPLACE FUNCTION refresh_document_performance_summary()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY public."DocumentPerformanceSummary";
END;
$$ LANGUAGE plpgsql;

-- Function to update document retrieval stats
CREATE OR REPLACE FUNCTION update_document_retrieval_stats()
RETURNS TRIGGER AS $$
BEGIN
    -- Update times_retrieved counter
    IF NEW.was_retrieved THEN
        UPDATE public."Documents"
        SET 
            times_retrieved = times_retrieved + 1,
            last_queried_at = NOW()
        WHERE id = NEW.document_id;
    END IF;
    
    -- Update times_cited counter
    IF NEW.was_cited THEN
        UPDATE public."Documents"
        SET times_cited = times_cited + 1
        WHERE id = NEW.document_id;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to auto-update document stats
DROP TRIGGER IF EXISTS trigger_update_document_stats ON public."QueryRunDocuments";

CREATE TRIGGER trigger_update_document_stats
    AFTER INSERT ON public."QueryRunDocuments"
    FOR EACH ROW
    EXECUTE FUNCTION update_document_retrieval_stats();

-- Function to calculate metadata completeness
CREATE OR REPLACE FUNCTION calculate_metadata_completeness(p_document_id BIGINT)
RETURNS BOOLEAN AS $$
DECLARE
    doc RECORD;
    required_fields INTEGER := 0;
    filled_fields INTEGER := 0;
BEGIN
    SELECT * INTO doc FROM public."Documents" WHERE id = p_document_id;
    
    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;
    
    -- Count required fields
    required_fields := 5; -- title, filename, collection, doc_id, source_type
    filled_fields := 0;
    
    IF doc.title IS NOT NULL AND doc.title != '' THEN filled_fields := filled_fields + 1; END IF;
    IF doc.filename IS NOT NULL AND doc.filename != '' THEN filled_fields := filled_fields + 1; END IF;
    IF doc.collection IS NOT NULL AND doc.collection != '' THEN filled_fields := filled_fields + 1; END IF;
    IF doc.doc_id IS NOT NULL AND doc.doc_id != '' THEN filled_fields := filled_fields + 1; END IF;
    IF doc.source_type IS NOT NULL AND doc.source_type != '' THEN filled_fields := filled_fields + 1; END IF;
    
    -- Optional but recommended fields
    IF doc.author IS NOT NULL AND doc.author != '' THEN filled_fields := filled_fields + 0.5; END IF;
    IF doc.year IS NOT NULL THEN filled_fields := filled_fields + 0.5; END IF;
    IF doc.document_type IS NOT NULL AND doc.document_type != '' THEN filled_fields := filled_fields + 0.5; END IF;
    IF doc.abstract IS NOT NULL AND doc.abstract != '' THEN filled_fields := filled_fields + 0.5; END IF;
    
    RETURN filled_fields >= required_fields;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- PHASE 9: PERMISSIONS
-- ============================================================================

-- Grant permissions on new tables
GRANT ALL ON public."Projects" TO authenticated, service_role, anon;
GRANT ALL ON public."DocumentIngestionJobs" TO authenticated, service_role, anon;
GRANT ALL ON public."QueryRuns" TO authenticated, service_role, anon;
GRANT ALL ON public."QueryRunDocuments" TO authenticated, service_role, anon;
GRANT ALL ON public."QueryRunEvaluations" TO authenticated, service_role, anon;

-- Grant permissions on materialized view
GRANT SELECT ON public."DocumentPerformanceSummary" TO authenticated, service_role, anon;

-- Grant function permissions
GRANT EXECUTE ON FUNCTION refresh_document_performance_summary TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION calculate_metadata_completeness TO authenticated, service_role;

-- ============================================================================
-- PHASE 10: INITIAL DATA
-- ============================================================================

-- Update metadata_complete flag for existing documents
UPDATE public."Documents"
SET metadata_complete = calculate_metadata_completeness(id);

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================
-- This migration adds:
-- - Enhanced document lifecycle tracking
-- - Document ingestion job history
-- - Query run tracking and evaluation
-- - Document performance analytics
-- - Automated statistics updates
--
-- Next steps:
-- 1. Implement document_manager.py for document operations
-- 2. Implement query_tracker.py for query run tracking
-- 3. Implement evaluation_manager.py for evaluations
-- 4. Build dashboard UI
-- ============================================================================
