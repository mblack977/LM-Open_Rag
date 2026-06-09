# Quick Start Guide - New Document System

## 🚀 Getting Started

### 1. Start the Application
```bash
cd "c:\Herb Project\LM-Open-Rag"
python main.py
```

### 2. Open Browser
Navigate to: `http://localhost:8000`

### 3. Click the Attach Button (📎)
Located in the sidebar, this opens the unified "Add Document" modal.

---

## 📝 Three Ways to Add Documents

### Option 1: Upload PDF (Fastest)
**When to use:** You have a PDF and want immediate processing

1. Click attach button (📎)
2. "Upload PDF" tab is already selected
3. Choose your PDF file
4. Click "Upload & Index"
5. Wait for processing
6. Done! Document is searchable

**Result:** Document with status `complete`

---

### Option 2: Add Manually (Catalog First)
**When to use:** You want to catalog documents before you have PDFs

1. Click attach button (📎)
2. Click "Add Manually" tab
3. Fill in the form:
   - **Title** (required)
   - Author, Year, Type, DOI, Abstract, Notes, Tags (optional)
4. Click "Save Document"
5. Done! Document is cataloged

**Later, attach PDF:**
1. Find document in list
2. Click "Attach PDF" button
3. Choose PDF file
4. Wait for processing

**Result:** Document with status `not_uploaded` → `complete` after PDF attached

---

### Option 3: Import CSV (Bulk Upload)
**When to use:** You have many documents in a spreadsheet

1. Click attach button (📎)
2. Click "Import CSV" tab
3. Click "Download CSV Template" (first time only)
4. Fill in your CSV file with document details
5. Save the CSV
6. Back in the app, select your CSV file
7. Click "Import Documents"
8. Review import summary
9. Done! All documents cataloged

**Later, attach PDFs:**
1. Filter list by status: "not_uploaded"
2. For each document, click "Attach PDF"
3. Choose PDF file

**Result:** Multiple documents with status `not_uploaded` → `complete` as PDFs are attached

---

## 🎨 Status Badges

Documents show colored status badges:

- **Gray** - not_uploaded (no PDF attached yet)
- **Blue** - queued (PDF uploaded, waiting to process)
- **Yellow** - processing (currently being indexed)
- **Green** - complete (fully processed and searchable)
- **Red** - failed (processing error occurred)

---

## 📊 CSV Format

Your CSV should have these columns (only `title` is required):

```csv
title,author,year,document_type,doi,abstract,notes,tags,filename
"Paper Title","Author Name",2023,"journal_article","10.1234/example","Abstract text","My notes","tag1,tag2",paper.pdf
```

**Document Types:**
- journal_article
- book
- book_chapter
- conference_paper
- thesis
- report
- other

---

## 🔧 Common Tasks

### Reset Everything (Clean Start)
1. Open Supabase Studio SQL Editor
2. Run `RESET_DOCUMENTS.sql`
3. All documents deleted
4. Ready to start fresh

### View All Documents Without PDFs
1. Go to Dashboard (if available)
2. Filter by status: "not_uploaded"
3. See all documents needing PDFs

### Attach PDF to Document
1. Find document with gray "not_uploaded" badge
2. Click "Attach PDF" button
3. Select PDF file
4. Wait for upload and processing

### Download CSV Template
1. Click attach button (📎)
2. Click "Import CSV" tab
3. Click "Download CSV Template" link
4. Open in Excel/Google Sheets

---

## ⚠️ Troubleshooting

### Modal Won't Open
- Refresh page
- Check browser console for errors
- Ensure JavaScript is enabled

### Upload Fails
- Check file size (max 50MB recommended)
- Ensure file is a valid PDF
- Check internet connection
- Try a different file

### CSV Import Shows Errors
- Download template and compare format
- Check for special characters
- Ensure year is a number
- Verify column headers match exactly

### Status Not Updating
- Refresh page
- Check server logs
- Wait a few moments for processing

---

## 📚 More Information

- **Full User Guide:** `DOCUMENT_INGESTION_GUIDE.md`
- **Testing Guide:** `UI_TESTING_GUIDE.md`
- **Technical Details:** `DOCUMENT_SYSTEM_SUMMARY.md`
- **Implementation:** `UI_IMPLEMENTATION_COMPLETE.md`

---

## ✅ Quick Test

Try this 2-minute test:

1. **Upload a PDF:**
   - Click attach (📎) → Upload PDF → Select file → Upload
   - ✅ Should complete and show in list

2. **Add manually:**
   - Click attach (📎) → Add Manually → Fill title → Save
   - ✅ Should show with "Attach PDF" button

3. **Import CSV:**
   - Click attach (📎) → Import CSV → Download template
   - Add 2 rows → Save → Import
   - ✅ Should show import summary

If all three work, you're ready to go! 🎉

---

## 🆘 Need Help?

1. Check the documentation files
2. Review browser console for errors
3. Check server logs
4. Refer to `UI_TESTING_GUIDE.md` for detailed test cases

---

**Happy document managing!** 📚✨
