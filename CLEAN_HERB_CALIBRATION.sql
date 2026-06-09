-- ============================================================================
-- CLEAN HERB_CALIBRATION COLLECTION
-- ============================================================================
-- This script removes all documents and chunks from the herb_calibration
-- collection to sync with the recreated Qdrant collection
-- ============================================================================

-- Delete all chunks from herb_calibration collection
DELETE FROM public."DocumentChunks" 
WHERE collection = 'herb_calibration';

-- Delete all documents from herb_calibration collection
DELETE FROM public."Documents" 
WHERE collection = 'herb_calibration';

-- Verify deletion
SELECT 
    'DocumentChunks' as table_name,
    COUNT(*) as remaining_records
FROM public."DocumentChunks" 
WHERE collection = 'herb_calibration'
UNION ALL
SELECT 
    'Documents' as table_name,
    COUNT(*) as remaining_records
FROM public."Documents" 
WHERE collection = 'herb_calibration';

-- ============================================================================
-- CLEANUP COMPLETE
-- ============================================================================
-- The herb_calibration collection is now empty in both Supabase and Qdrant.
-- You can now re-upload your documents.
-- ============================================================================
