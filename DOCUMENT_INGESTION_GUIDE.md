# Document Ingestion Guide

This guide explains the three ways to add documents to the Herb Project system.

## Overview

The system supports three document ingestion workflows:

1. **Upload & Ingest** - Upload a PDF and automatically extract metadata
2. **Add Document Manually** - Enter document details manually, optionally attach PDF later
3. **Bulk Import from CSV** - Import multiple document records from a CSV file

## Workflow 1: Upload & Ingest

**Use when:** You have a PDF file and want the system to automatically extract metadata.

**Steps:**
1. Click "Add Document" button
2. Select "Upload PDF" tab
3. Choose your PDF file
4. Click "Upload & Index"
5. System will:
   - Extract metadata (title, author, etc.)
   - Process and chunk the document
   - Create embeddings
   - Make it searchable

**API Endpoint:** `POST /upload`
- Existing endpoint that handles PDF upload and processing
- Automatically creates document record with extracted metadata

## Workflow 2: Add Document Manually

**Use when:** You want to catalog a document without uploading the PDF yet, or the PDF is not available.

**Steps:**
1. Click "Add Document" button
2. Fill in document details:
   - Title (required)
   - Author
   - Year
   - Document Type (journal_article, book, conference_paper, etc.)
   - DOI
   - Abstract
   - Notes
   - Tags
3. Click "Save Document"
4. Document is created with status: `not_uploaded`
5. Later, you can attach a PDF:
   - Find the document in the list
   - Click "Attach PDF"
   - Upload the file
   - System will process and index it

**API Endpoints:**
- `POST /api/documents/add-manual` - Create document record
- `POST /api/documents/attach-pdf/{document_id}` - Attach PDF later

## Workflow 3: Bulk Import from CSV

**Use when:** You have a collection of documents cataloged in a spreadsheet or database.

**Steps:**
1. Prepare your CSV file (see template: `document_import_template.csv`)
2. Click "Add Document" button
3. Select "Import from CSV" tab
4. Choose your CSV file
5. Select the target collection
6. Click "Import"
7. System will:
   - Create document records for all rows
   - Show import summary (success/errors)
   - Documents without file_path will have status: `not_uploaded`
   - You can attach PDFs individually later

**CSV Format:**

Required columns:
- `title` - Document title

Optional columns:
- `author` - Author name(s)
- `year` - Publication year (integer)
- `document_type` - Type of document
- `doi` - Digital Object Identifier
- `abstract` - Document abstract
- `notes` - Your notes about the document
- `tags` - Comma-separated tags
- `filename` - Filename for the PDF (if you have it)
- `file_path` - Full path to PDF file (if already on server)

**Example CSV:**
```csv
title,author,year,document_type,doi,abstract,notes,tags,filename
"Academic Self-Concept Study","Marsh, H.",2011,"journal_article","10.1234/example","Study on self-concept","Important research","education,psychology",marsh_2011.pdf
```

**API Endpoint:** `POST /api/documents/bulk-import`

## Document Status Flow

Documents go through these statuses:

1. **not_uploaded** - Document record created, no PDF attached
2. **queued** - PDF attached, waiting for processing
3. **processing** - Currently being chunked and indexed
4. **complete** - Fully processed and searchable
5. **failed** - Processing error occurred

## Attaching PDFs to Imported Documents

After bulk import, you can attach PDFs:

1. Go to document list
2. Filter by `ingestion_status = not_uploaded`
3. For each document:
   - Click "Attach PDF"
   - Upload the file
   - System processes it automatically

## Database Reset

To start fresh and delete all documents:

1. Open Supabase Studio SQL Editor
2. Run the script: `RESET_DOCUMENTS.sql`
3. This will delete:
   - All documents
   - All document chunks
   - All query runs and evaluations
   - All ingestion jobs

**WARNING:** This is permanent and cannot be undone!

## Best Practices

### For Manual Entry:
- Fill in as many fields as possible for better searchability
- Use consistent author name formats
- Add descriptive tags
- Include abstracts when available

### For CSV Import:
- Use the provided template as a starting point
- Validate your CSV before importing
- Keep backups of your CSV files
- Import in batches if you have many documents

### For PDF Upload:
- Use descriptive filenames
- Ensure PDFs are text-based (not scanned images)
- Check file size limits
- Verify metadata extraction results

## Metadata Completeness

The system tracks metadata completeness:

**Required fields:**
- title
- filename
- collection
- doc_id
- source_type

**Recommended fields (need at least 2):**
- author
- year
- document_type
- abstract

Documents with complete metadata are flagged as `metadata_complete = true`.

## API Reference

### Create Document Manually
```http
POST /api/documents/add-manual
Content-Type: application/json

{
  "collection": "my_collection",
  "title": "Document Title",
  "author": "Author Name",
  "year": 2023,
  "document_type": "journal_article",
  "doi": "10.1234/example",
  "abstract": "Abstract text",
  "notes": "My notes",
  "tags": ["tag1", "tag2"]
}
```

### Attach PDF
```http
POST /api/documents/attach-pdf/{document_id}
Content-Type: multipart/form-data

file: <PDF file>
```

### Bulk Import CSV
```http
POST /api/documents/bulk-import
Content-Type: multipart/form-data

file: <CSV file>
collection: my_collection
```

### List Documents
```http
GET /api/documents?collection=my_collection&ingestion_status=not_uploaded
```

## Troubleshooting

### Import Errors
- Check CSV format matches template
- Ensure year values are integers
- Verify collection exists
- Check for duplicate doc_ids

### PDF Processing Errors
- Verify PDF is not corrupted
- Check file size is reasonable
- Ensure PDF contains extractable text
- Review processing logs

### Missing Metadata
- Update document record via PATCH endpoint
- Re-upload PDF to re-extract metadata
- Manually edit fields in UI

## Next Steps

After ingesting documents:
1. Review document list
2. Attach PDFs to imported records
3. Verify metadata completeness
4. Test search and retrieval
5. Monitor ingestion jobs
6. Review document performance analytics
