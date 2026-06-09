# PDF Upload & Document Linking - Fixed! ✅

## Problem
When you manually created a document entry and then uploaded a PDF, they weren't being linked together. The document showed:
- PDF: ❌
- Status: `not_uploaded`
- No metadata extraction

## Solution Implemented

### 1. **Smart PDF Attachment** - `@main.py:938-955`
When uploading a PDF, the system now:
1. Checks if a document with the same filename already exists (without PDF)
2. If found, attaches the PDF to that existing document
3. If not found, creates a new document

### 2. **Upload PDF Button** - `@dashboard.js:502-504`
Added a "📎 Upload PDF" button for documents without PDFs:
- Shows only when `pdf_attached = false`
- Opens file picker directly
- Attaches PDF to the specific document

### 3. **Updated Upload Logic** - `@main.py:973-1010`
When attaching to existing document:
- Updates `pdf_attached = true`
- Sets `ingestion_status = 'processing'` → `'complete'`
- Preserves existing metadata (title, author, year, etc.)
- Stores chunks with the document's metadata

## How to Use

### **Workflow 1: Manual Entry First**
1. Click "Add Document" → "Add Manually"
2. Enter title, author, year, etc.
3. Submit (creates document with `pdf_attached = false`)
4. In the Documents tab, click "📎 Upload PDF" button
5. Select the PDF file
6. ✅ PDF is attached and ingested!

### **Workflow 2: Upload PDF Directly**
1. Click "Add Document" → "Upload PDF"
2. Select PDF file
3. ✅ Document created with PDF attached

### **Workflow 3: Upload PDF with Matching Filename**
1. Manually create document with title: `"Gan (2025) Retrieval Augmented Generation.pdf"`
2. Upload PDF with filename: `"Gan (2025) Retrieval Augmented Generation.pdf"`
3. ✅ System automatically links them together!

## What Gets Updated

When PDF is attached to existing document:

**Before:**
```
Title: Gan (2025) Retrieval Augmented Generation
PDF: ❌
Status: not_uploaded
```

**After:**
```
Title: Gan (2025) Retrieval Augmented Generation
PDF: ✅
Status: complete
Chunks: 45
```

## API Endpoints

### POST /api/documents/attach-pdf/{document_id}
Attaches a PDF to an existing document.

**Request:**
- `file`: PDF file (multipart/form-data)

**Response:**
```json
{
  "status": "success",
  "document_id": 123,
  "ingestion_status": "complete",
  "message": "PDF attached and ingested successfully"
}
```

## Files Changed

1. **`main.py`** - Smart PDF attachment logic
2. **`static/dashboard.js`** - Upload PDF button and handler
3. **`PDF_UPLOAD_FIX.md`** - This documentation

## Notes

- The system matches documents by **exact filename** when auto-linking
- Metadata (title, author, year) is preserved from manual entry
- Chunks are stored with the document's metadata, not just filename
- Ingestion status updates automatically: `not_uploaded` → `processing` → `complete`
