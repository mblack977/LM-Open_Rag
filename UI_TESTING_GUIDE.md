# UI Testing Guide - Document Ingestion System

## Overview
This guide will help you test the new unified document ingestion system with three workflows.

## Prerequisites
1. Ensure Supabase is configured and running
2. Run the migration: `DOCUMENT_EVALUATION_MIGRATION.sql` (if not already done)
3. Start the application: `python main.py`
4. Open browser to `http://localhost:8000`

## UI Components Added

### 1. Unified "Add Document" Modal
- **Location:** Accessible via the attach button (📎) in the chat interface
- **Features:**
  - Three tabs: Upload PDF, Add Manually, Import CSV
  - Tab switching
  - Form validation
  - Progress indicators
  - Status messages

### 2. Status Badges
- **Colors:**
  - Gray: not_uploaded
  - Blue: queued
  - Yellow: processing
  - Green: complete
  - Red: failed

### 3. Attach PDF Button
- Shows on documents where `pdf_attached = false`
- Opens file picker
- Uploads PDF to existing document record

## Test Plan

### Test 1: Upload PDF Workflow
**Objective:** Verify PDF upload and automatic metadata extraction

**Steps:**
1. Click the attach button (📎) in the sidebar
2. Verify "Add Document" modal opens
3. Verify "Upload PDF" tab is active by default
4. Click "Select PDF File" and choose a PDF
5. Click "Upload & Index"
6. Verify progress bar appears and updates
7. Verify success message appears
8. Verify modal closes automatically
9. Verify document appears in the list (refresh if needed)
10. Verify document has status badge "complete"

**Expected Results:**
- ✅ PDF uploads successfully
- ✅ Metadata extracted automatically
- ✅ Document appears in list
- ✅ Status shows "complete"

**Test Data:**
- Use any academic PDF file
- Recommended: A paper with clear title and author metadata

---

### Test 2: Add Document Manually Workflow
**Objective:** Verify manual document entry without PDF

**Steps:**
1. Click the attach button (📎)
2. Click "Add Manually" tab
3. Fill in the form:
   - Title: "Test Document - Manual Entry"
   - Author: "Test Author"
   - Year: 2023
   - Document Type: "Journal Article"
   - DOI: "10.1234/test"
   - Abstract: "This is a test abstract"
   - Notes: "Test notes"
   - Tags: "test, manual, demo"
4. Click "Save Document"
5. Verify success message
6. Verify modal closes
7. Refresh the page
8. Find the document in the list
9. Verify status badge shows "not_uploaded"
10. Verify "Attach PDF" button is visible

**Expected Results:**
- ✅ Document created successfully
- ✅ All metadata saved correctly
- ✅ Status shows "not_uploaded"
- ✅ "Attach PDF" button appears

**Test Data:**
```
Title: Academic Self-Concept and Achievement
Author: Marsh, H. W.
Year: 2011
Type: journal_article
DOI: 10.1111/j.2044-8279.2011.02045.x
Abstract: This study examines the relationship between academic self-concept and achievement.
Notes: Important foundational research
Tags: education, psychology, self-concept
```

---

### Test 3: Attach PDF to Existing Document
**Objective:** Verify PDF attachment to manually created document

**Steps:**
1. Locate the document created in Test 2
2. Click the "Attach PDF" button
3. Select a PDF file from the file picker
4. Wait for upload to complete
5. Verify success alert appears
6. Verify page refreshes
7. Verify document status changes from "not_uploaded" to "queued" or "complete"
8. Verify "Attach PDF" button disappears

**Expected Results:**
- ✅ PDF uploads successfully
- ✅ Status updates to "queued" or "complete"
- ✅ "Attach PDF" button no longer visible
- ✅ Document is now searchable

---

### Test 4: Import CSV Workflow
**Objective:** Verify bulk import from CSV file

**Steps:**
1. Download the CSV template:
   - Click attach button (📎)
   - Click "Import CSV" tab
   - Click "Download CSV Template"
2. Open the template in Excel/Sheets
3. Add 3-5 test documents with varying data:
   - Some with all fields filled
   - Some with minimal fields
   - Mix of document types
4. Save the CSV file
5. Return to the application
6. Click attach button (📎)
7. Click "Import CSV" tab
8. Click "Select CSV File" and choose your file
9. Click "Import Documents"
10. Verify import progress message
11. Verify import summary appears showing:
    - Number of documents imported
    - Number of errors (should be 0)
12. Verify modal closes after 3 seconds
13. Refresh the page
14. Verify all documents appear in the list
15. Verify all have status "not_uploaded"

**Expected Results:**
- ✅ CSV parses correctly
- ✅ All valid rows imported
- ✅ Import summary shows correct counts
- ✅ Documents appear in list
- ✅ All show "not_uploaded" status

**Test CSV Data:**
```csv
title,author,year,document_type,doi,abstract,notes,tags,filename
"Self-Concept Research","Marsh, H.",2011,"journal_article","10.1111/test1","Abstract 1","Notes 1","education,psychology",marsh_2011.pdf
"Achievement Study","Smith, J.",2020,"book","10.1234/test2","Abstract 2","Notes 2","achievement,motivation",smith_2020.pdf
"Meta-Analysis","Jones, A.",2019,"conference_paper","10.5678/test3","Abstract 3","Notes 3","meta-analysis,research",jones_2019.pdf
```

---

### Test 5: Import CSV with Errors
**Objective:** Verify error handling in CSV import

**Steps:**
1. Create a CSV with intentional errors:
   - Invalid year (text instead of number)
   - Missing required title field
   - Malformed data
2. Import the CSV
3. Verify import summary shows:
   - Some documents imported
   - Some errors
4. Verify error list displays specific row numbers and error messages
5. Verify successfully imported documents appear in list

**Expected Results:**
- ✅ Valid rows imported successfully
- ✅ Invalid rows reported with specific errors
- ✅ Error messages are clear and helpful
- ✅ Process doesn't crash

---

### Test 6: Status Badge Display
**Objective:** Verify status badges display correctly

**Steps:**
1. Create documents with different statuses:
   - Manual entry (not_uploaded)
   - Upload PDF (complete)
   - Attach PDF to manual entry (queued → complete)
2. Verify each status badge:
   - Displays correct text
   - Has correct color
   - Is properly formatted

**Expected Results:**
- ✅ not_uploaded: Gray badge
- ✅ queued: Blue badge
- ✅ processing: Yellow badge
- ✅ complete: Green badge
- ✅ failed: Red badge

---

### Test 7: Tab Switching
**Objective:** Verify tab navigation works correctly

**Steps:**
1. Open Add Document modal
2. Click each tab in sequence
3. Verify:
   - Tab button highlights correctly
   - Content switches appropriately
   - Previous tab content is hidden
   - Form data persists when switching back

**Expected Results:**
- ✅ Tabs switch smoothly
- ✅ Only one tab active at a time
- ✅ Content displays correctly
- ✅ No visual glitches

---

### Test 8: Form Validation
**Objective:** Verify form validation works

**Steps:**
1. **Upload PDF Tab:**
   - Try submitting without selecting file
   - Verify error message
2. **Add Manually Tab:**
   - Try submitting with empty title
   - Verify error message
   - Fill title and submit
   - Verify success
3. **Import CSV Tab:**
   - Try submitting without selecting file
   - Verify error message

**Expected Results:**
- ✅ Required fields enforced
- ✅ Clear error messages
- ✅ Forms don't submit with invalid data

---

### Test 9: Modal Close Behavior
**Objective:** Verify modal closes correctly

**Steps:**
1. Open modal
2. Test each close method:
   - Click X button
   - Click Cancel button
   - Click outside modal (overlay)
3. Verify:
   - Modal closes
   - Forms reset
   - Status messages clear

**Expected Results:**
- ✅ All close methods work
- ✅ Forms reset on close
- ✅ No data persists between opens

---

### Test 10: End-to-End Workflow
**Objective:** Complete workflow from import to search

**Steps:**
1. Import 5 documents via CSV (no PDFs)
2. Verify all show "not_uploaded"
3. Attach PDFs to 3 of them
4. Wait for processing to complete
5. Verify statuses update to "complete"
6. Test search functionality
7. Verify only documents with PDFs are searchable
8. Verify metadata from manual entry is preserved

**Expected Results:**
- ✅ Complete workflow works smoothly
- ✅ Documents with PDFs are searchable
- ✅ Documents without PDFs are cataloged but not searchable
- ✅ Metadata integrity maintained

---

## Common Issues & Solutions

### Issue: Modal doesn't open
**Solution:** 
- Check browser console for errors
- Verify `document-manager.js` is loaded
- Check that `documentManager` is initialized

### Issue: Upload fails
**Solution:**
- Check file size limits
- Verify PDF is valid
- Check server logs
- Ensure collection exists

### Issue: CSV import shows all errors
**Solution:**
- Verify CSV format matches template
- Check for special characters
- Ensure proper encoding (UTF-8)
- Verify column headers match exactly

### Issue: Status badges don't show
**Solution:**
- Refresh page
- Check CSS is loaded (v=14)
- Verify document has `ingestion_status` field

### Issue: Attach PDF button doesn't appear
**Solution:**
- Verify document has `pdf_attached = false`
- Check document list rendering code
- Refresh page

---

## Browser Testing

Test in multiple browsers:
- ✅ Chrome/Edge (Chromium)
- ✅ Firefox
- ✅ Safari (if on Mac)

Verify:
- Modal displays correctly
- File pickers work
- Forms submit properly
- Styles render correctly

---

## Performance Testing

### Large CSV Import
1. Create CSV with 100+ documents
2. Import and measure:
   - Import time
   - Browser responsiveness
   - Error handling
   - Memory usage

**Expected:** Should handle 100+ documents without issues

### Multiple Concurrent Uploads
1. Open multiple tabs
2. Upload PDFs simultaneously
3. Verify no conflicts or errors

---

## Accessibility Testing

1. **Keyboard Navigation:**
   - Tab through form fields
   - Use Enter to submit
   - Use Esc to close modal

2. **Screen Reader:**
   - Test with screen reader
   - Verify labels are read correctly
   - Verify status messages are announced

---

## Cleanup After Testing

1. Run `RESET_DOCUMENTS.sql` to clean test data
2. Verify all test documents removed
3. Verify sequences reset
4. Ready for production use

---

## Success Criteria

All tests should pass with:
- ✅ No JavaScript errors in console
- ✅ No broken UI elements
- ✅ All workflows complete successfully
- ✅ Data persists correctly
- ✅ Status updates accurately
- ✅ Error handling works properly

---

## Reporting Issues

If you find bugs, document:
1. Test number and step
2. Expected vs actual behavior
3. Browser and version
4. Console errors (if any)
5. Screenshots (if applicable)

---

## Next Steps After Testing

1. Deploy to production
2. Monitor error logs
3. Gather user feedback
4. Iterate on UX improvements
5. Add more document types as needed
