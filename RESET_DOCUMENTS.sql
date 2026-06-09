-- ============================================================================
-- RESET DOCUMENTS - Clean Start Script
-- ============================================================================
-- This script deletes all ingested documents and resets the document system
-- WARNING: This will permanently delete all document data!
-- Run this in Supabase Studio SQL Editor
-- ============================================================================

-- Step 1: Delete all query run evaluations
DELETE FROM public."QueryRunEvaluations";

-- Step 2: Delete all query run documents
DELETE FROM public."QueryRunDocuments";

-- Step 3: Delete all query runs
DELETE FROM public."QueryRuns";

-- Step 4: Delete all document ingestion jobs
DELETE FROM public."DocumentIngestionJobs";

-- Step 5: Delete all document chunks
DELETE FROM public."DocumentChunks";

-- Step 6: Delete all documents
DELETE FROM public."Documents";

-- Step 7: Refresh the materialized view
REFRESH MATERIALIZED VIEW public."DocumentPerformanceSummary";

-- Step 8: Reset sequences (optional - starts IDs from 1 again)
ALTER SEQUENCE IF EXISTS "Documents_id_seq" RESTART WITH 1;
ALTER SEQUENCE IF EXISTS "DocumentChunks_id_seq" RESTART WITH 1;

-- Verification queries
SELECT 'Documents' as table_name, COUNT(*) as count FROM public."Documents"
UNION ALL
SELECT 'DocumentChunks', COUNT(*) FROM public."DocumentChunks"
UNION ALL
SELECT 'QueryRuns', COUNT(*) FROM public."QueryRuns"
UNION ALL
SELECT 'QueryRunDocuments', COUNT(*) FROM public."QueryRunDocuments"
UNION ALL
SELECT 'QueryRunEvaluations', COUNT(*) FROM public."QueryRunEvaluations"
UNION ALL
SELECT 'DocumentIngestionJobs', COUNT(*) FROM public."DocumentIngestionJobs";

-- ============================================================================
-- RESET COMPLETE
-- ============================================================================
