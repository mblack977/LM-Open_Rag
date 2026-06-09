# Bug Fixes and Feature Additions Summary

## Date: April 28, 2026

This document summarizes all the fixes and enhancements made to address the reported issues.

---

## Issue 1: Collection Card Image Not Updating After Upload ✅

**Problem:** When uploading an image for a collection, the image was not displaying on the collection card.

**Root Cause:** 
- Frontend code was checking for `c.image` property, but the backend returns `image_url`
- Image display logic was inconsistent across different views

**Files Modified:**
- `static/app.js` - Fixed collection card image display (lines 690-701, 762-768)
- `static/dashboard.js` - Fixed dashboard collection cards (lines 907-912, 1021-1027)

**Changes Made:**
1. Updated collection card rendering to check for both `image` and `image_url` properties
2. Updated image source to use `image_url || image || fallback` pattern
3. Applied fix to all collection views: main app, edit view, and dashboard

---

## Issue 2: Document Count Showing Incorrect Numbers ✅

**Problem:** Collection cards were showing 7 documents when only 3 were actually loaded/complete.

**Root Cause:** 
- Document count query was counting ALL documents in the collection, including those with `ingestion_status != 'complete'` or `is_active = false`

**Files Modified:**
- `src/db_collection_manager.py` - Updated `list_collections()` method (lines 99-109)

**Changes Made:**
1. Modified document count query to only count documents with:
   - `ingestion_status = 'complete'`
   - `is_active = true`
2. This ensures only successfully ingested and active documents are counted

---

## Issue 3: Documents Not Loading on Dashboard "All Documents" View ✅

**Problem:** When clicking on the dashboard to show documents, the list would not load unless a specific collection was selected or the page was refreshed.

**Root Cause:** 
- The `switchTab()` function was not calling `loadDocuments()` when switching to the documents tab
- Documents would only load if explicitly triggered by collection filter change or refresh

**Files Modified:**
- `static/dashboard.js` - Updated `switchTab()` method (lines 425-436)

**Changes Made:**
1. Added `loadDocuments()` call when switching to the 'documents' tab
2. This ensures documents are loaded automatically when the tab is activated

---

## Issue 4: Add APA7 Reference Field ✅

**Problem:** Need to add an APA 7th edition reference field to the Documents table and CSV import functionality for proper citation management.

**Implementation:**

### Database Changes
**New File:** `ADD_APA7_FIELD.sql`
- Adds `apa7_reference` TEXT column to Documents table
- Creates index for searching by APA reference
- Includes migration safety checks

### Backend Changes
**Files Modified:**
- `src/document_manager.py`:
  - Added `apa7_reference` parameter to `create_document()` function (line 32)
  - Added `apa7_reference` to document row creation (line 75-76)
  - Added `apa7_reference` to CSV field mapping in `bulk_import_documents()` (line 632)

### CSV Template Updates
**Files Modified:**
- `document_import_template.csv` - Added apa7_reference column with examples
- `static/document_import_template.csv` - Added apa7_reference column with examples

**Example APA7 References in Templates:**
```
"Smith, J. (2023). Example article title. Journal of Educational Psychology, 115(3), 456-478. https://doi.org/10.1234/example"
"Jones, A., & Brown, B. (2022). Another research paper. In Proceedings of the International Conference on Education (pp. 123-145). Academic Press. https://doi.org/10.5678/example2"
```

### Frontend Changes

#### HTML Forms Updated:
1. **Dashboard Create Document Form** (`templates/dashboard.html` lines 242-245)
   - Added APA 7 Reference textarea field

2. **Collection Manual Entry Form** (`templates/index.html` lines 430-433)
   - Added APA 7 Reference textarea field with placeholder

3. **Main Manual Entry Form** (`templates/index.html` lines 661-664)
   - Added APA 7 Reference textarea field with placeholder

4. **Dashboard Collection Manual Form** (`templates/dashboard.html` lines 450-453)
   - Added APA 7 Reference textarea field with placeholder

#### JavaScript Updates:
1. **document-manager.js**:
   - Collection manual form payload (line 147)
   - Main manual form payload (line 369)

2. **dashboard.js**:
   - Dashboard manual form payload (line 282)

#### CSV Format Descriptions Updated:
- `templates/dashboard.html` (line 471)
- `templates/index.html` (lines 451, 682)

All CSV import hints now show: `title, author, year, document_type, doi, abstract, notes, tags, filename, apa7_reference`

---

## Migration Instructions

### To Apply These Fixes:

1. **Run the SQL Migration:**
   ```bash
   # Execute the SQL migration to add the apa7_reference column
   psql -h your-supabase-host -U postgres -d postgres -f ADD_APA7_FIELD.sql
   ```
   Or run it through the Supabase SQL Editor.

2. **Restart the Application:**
   ```bash
   # The Python and JavaScript changes will be picked up automatically
   # Just restart your FastAPI server if it's running
   ```

3. **Clear Browser Cache:**
   - Users should clear their browser cache or do a hard refresh (Ctrl+F5) to get the updated JavaScript files

4. **Download New CSV Template:**
   - Users should download the updated CSV template which now includes the apa7_reference column

---

## Testing Checklist

- [x] Collection image uploads and displays correctly on cards
- [x] Collection image displays in edit view
- [x] Document counts show only completed, active documents
- [x] Documents load automatically when switching to Documents tab
- [x] Documents load when "All Collections" is selected
- [x] APA7 reference field appears in all manual entry forms
- [x] APA7 reference is saved when creating documents manually
- [x] APA7 reference is imported from CSV files
- [x] CSV template includes apa7_reference column with examples
- [x] CSV format descriptions updated everywhere

---

## Notes

- The APA7 reference field is **optional** - documents can be created without it
- The field accepts any text format, allowing flexibility for different citation styles if needed
- When querying documents, the apa7_reference can be returned with results for proper attribution
- All existing documents will have `apa7_reference = NULL` until updated

---

## Future Enhancements (Optional)

Consider implementing:
1. APA7 reference validation or formatting assistance
2. Auto-generation of APA7 references from DOI
3. Display of APA7 references in query results
4. Bulk update tool for adding APA7 references to existing documents
