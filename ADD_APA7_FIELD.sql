-- ============================================================================
-- ADD APA7 REFERENCE FIELD TO DOCUMENTS TABLE
-- ============================================================================
-- This migration adds an apa7_reference field to the Documents table
-- to store APA 7th edition formatted citations for each document
-- ============================================================================

-- Add apa7_reference column to Documents table
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='Documents' AND column_name='apa7_reference') THEN
        ALTER TABLE public."Documents" ADD COLUMN apa7_reference TEXT;
        COMMENT ON COLUMN public."Documents".apa7_reference IS 'APA 7th edition formatted citation for this document';
    END IF;
END $$;

-- Create index for searching by APA reference
CREATE INDEX IF NOT EXISTS idx_documents_apa7_reference ON public."Documents"(apa7_reference);

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================
-- The apa7_reference field can now be used to store formatted citations
-- that will be returned with query results for proper attribution.
-- ============================================================================
