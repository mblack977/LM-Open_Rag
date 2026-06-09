-- Add doi and year columns to Documents table
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='Documents' AND column_name='doi') THEN
        ALTER TABLE public."Documents" ADD COLUMN doi TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='Documents' AND column_name='year') THEN
        ALTER TABLE public."Documents" ADD COLUMN year TEXT;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_documents_doi  ON public."Documents"(doi);
CREATE INDEX IF NOT EXISTS idx_documents_year ON public."Documents"(year);
