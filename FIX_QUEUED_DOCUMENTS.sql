-- Fix documents stuck in "queued" status
-- This updates documents that have chunks but are still marked as "queued"

-- STEP 1: Show current queued documents
SELECT 
    id,
    title,
    collection,
    pdf_attached,
    ingestion_status,
    (SELECT COUNT(*) FROM public."DocumentChunks" dc WHERE dc.collection = d.collection AND dc.doc_id = d.doc_id) as actual_chunk_count,
    chunk_count as recorded_chunk_count,
    created_at
FROM public."Documents" d
WHERE ingestion_status = 'queued'
ORDER BY created_at DESC;

-- STEP 2: Update documents with chunks to "complete" status
UPDATE public."Documents" d
SET 
    ingestion_status = 'complete',
    chunk_count = (
        SELECT COUNT(*) 
        FROM public."DocumentChunks" dc 
        WHERE dc.collection = d.collection 
        AND dc.doc_id = d.doc_id
    )
WHERE 
    d.ingestion_status = 'queued'
    AND EXISTS (
        SELECT 1 
        FROM public."DocumentChunks" dc 
        WHERE dc.collection = d.collection 
        AND dc.doc_id = d.doc_id
    );

-- STEP 3: Update documents without chunks to "failed" status
UPDATE public."Documents" d
SET 
    ingestion_status = 'failed',
    chunk_count = 0
WHERE 
    d.ingestion_status = 'queued'
    AND NOT EXISTS (
        SELECT 1 
        FROM public."DocumentChunks" dc 
        WHERE dc.collection = d.collection 
        AND dc.doc_id = d.doc_id
    );

-- STEP 4: Show the results
SELECT 
    ingestion_status,
    COUNT(*) as count,
    SUM(CASE WHEN pdf_attached THEN 1 ELSE 0 END) as with_pdf
FROM public."Documents"
GROUP BY ingestion_status
ORDER BY ingestion_status;

-- STEP 5: Show recently updated documents
SELECT 
    id,
    title,
    collection,
    pdf_attached,
    ingestion_status,
    chunk_count,
    updated_at
FROM public."Documents"
WHERE ingestion_status IN ('complete', 'failed')
ORDER BY updated_at DESC
LIMIT 20;
