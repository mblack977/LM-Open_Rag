# Document Operations & Evaluation System Guide

## Overview

This system provides comprehensive document lifecycle management and query evaluation capabilities for your RAG platform. It consists of two connected layers:

1. **Document Operations Layer** - Manages document metadata, ingestion tracking, and lifecycle
2. **Evaluation & Experimentation Layer** - Tracks query runs, evaluates response quality, and provides analytics

## Table of Contents

- [Getting Started](#getting-started)
- [Document Management](#document-management)
- [Query Tracking](#query-tracking)
- [Evaluation System](#evaluation-system)
- [Analytics Dashboard](#analytics-dashboard)
- [API Reference](#api-reference)
- [Database Schema](#database-schema)

## Getting Started

### 1. Run the Database Migration

First, apply the database migration to add the new tables and fields:

```bash
# Connect to your Supabase database and run:
psql -h your-host -U your-user -d your-db -f DOCUMENT_EVALUATION_MIGRATION.sql
```

This creates:
- Extended `Documents` table with lifecycle tracking
- `DocumentIngestionJobs` table for ingestion history
- `Projects` table for document grouping
- `QueryRuns` table for query tracking
- `QueryRunDocuments` table for document usage tracking
- `QueryRunEvaluations` table for quality scoring
- `DocumentPerformanceSummary` materialized view for analytics

### 2. Access the Dashboard

Navigate to `http://localhost:8080/dashboard` to access the dashboard interface.

### 3. Start Using the System

The system automatically tracks:
- Document uploads and ingestion
- Query runs and retrieval results
- Document usage in responses
- Performance metrics

## Document Management

### Two Workflow Options

#### Option A: Upload PDF First (Traditional)

1. Click "📤 Upload PDF" on the dashboard
2. Select your PDF file
3. System automatically:
   - Creates document record
   - Extracts metadata
   - Processes and chunks the document
   - Creates ingestion job record

#### Option B: Create Metadata First (New)

1. Click "+ New Document" on the dashboard
2. Enter document metadata:
   - Title (required)
   - Document type (article, report, thesis, etc.)
   - Author
   - Year
   - DOI
   - Abstract
   - Notes
3. Click "Create"
4. Later, attach PDF by clicking "Attach PDF" action

### Document Statuses

Documents progress through these statuses:

- **not_uploaded** - Metadata exists but no PDF attached
- **queued** - PDF attached, waiting for processing
- **processing** - Currently being ingested
- **complete** - Successfully processed and indexed
- **failed** - Ingestion failed (check error message)

### Document Fields

**Required Fields:**
- Title
- Filename
- Collection
- Source type

**Recommended Fields:**
- Author
- Year
- Document type
- Abstract

**Tracking Fields (Auto-populated):**
- PDF attached status
- Ingestion status
- Chunk count
- Times retrieved
- Times cited
- Last queried date
- Average quality score

### Managing Documents

**View Documents:**
- Filter by status, type, or collection
- Search by title, author, or notes
- Sort by retrieval count, citations, or score

**Edit Metadata:**
- Click "Edit" button on any document
- Update any metadata field
- System recalculates metadata completeness

**Delete Documents:**
- Soft delete (marks as inactive, preserves data)
- Hard delete (permanently removes, use with caution)

## Query Tracking

### Automatic Tracking

Every query automatically creates a `QueryRun` record that captures:

**Query Details:**
- User query text
- Final response
- Collection used
- Session and message IDs (if from chat)

**Retrieval Configuration:**
- Retrieval mode (BM25, vector, hybrid, etc.)
- Retrieval profile used
- Top-k values
- Reranker settings

**LLM Configuration:**
- Model used
- Embedding model
- Temperature
- Prompt version

**Performance Metrics:**
- Total response time
- Retrieval time
- LLM generation time
- Token counts
- Estimated cost

### Document Usage Tracking

For each query, the system tracks three stages:

1. **Retrieved** - Documents returned by retrieval system
2. **In Context** - Documents sent to LLM in prompt
3. **Cited** - Documents referenced in final response

This enables analysis of:
- Which documents are retrieved but never used
- Which documents contribute to high-quality responses
- Retrieval precision vs. recall

### Use Case Types

Tag queries with use case types for targeted analysis:

- `literature_review` - Synthesizing research findings
- `document_qa` - Answering specific questions
- `policy_extraction` - Extracting policy information
- `thematic_synthesis` - Identifying themes
- `stats_help` - Statistical analysis assistance

## Evaluation System

### Quick Evaluation (Thumbs Up/Down)

1. Go to "⭐ Evaluation" tab
2. Find the query you want to evaluate
3. Click "⭐ Evaluate"
4. Give thumbs up (5 stars) or thumbs down (1 star)

### Detailed Evaluation

For comprehensive quality assessment:

1. Click "⭐ Evaluate" on a query
2. Rate on multiple dimensions (1-5 scale):
   - **Overall Quality** - General satisfaction
   - **Accuracy** - Factual correctness
   - **Relevance** - How well it answered the question
   - **Completeness** - Whether answer was thorough
   - **Clarity** - Writing quality and understandability
   - **Source Usefulness** - Quality of retrieved documents
   - **Citation Quality** - Appropriateness of citations

3. Flag issues:
   - Check "Contains hallucinations" if applicable

4. Add feedback:
   - Optional text feedback for context

### Evaluation Best Practices

**When to Evaluate:**
- Immediately after receiving a response (while fresh)
- When you notice particularly good or bad responses
- Periodically review recent queries

**What to Look For:**
- Factual errors or hallucinations
- Missing key information
- Irrelevant or off-topic content
- Poor source selection
- Citation accuracy

**Use Evaluations To:**
- Identify which settings work best
- Find documents that contribute to poor responses
- Compare model performance
- Track quality improvements over time

## Analytics Dashboard

### Documents Tab

**Summary Metrics:**
- Total documents
- Documents with retrievals
- Documents with citations
- Unused documents
- Documents needing attention

**Rankings:**
- Most retrieved documents
- Most cited documents
- Highest rated documents
- Retrieved but never cited (potential low-quality sources)

**Actions:**
- Create new documents
- Upload PDFs
- Edit metadata
- View document details

### Ingestion Tab

**Queue Management:**
- View queued jobs
- Monitor processing jobs
- Check completed jobs
- Review failed jobs with error logs

**Bulk Operations:**
- Retry failed jobs
- Clear completed jobs
- Monitor processing progress

### Analytics Tab

**Document Performance:**
- Which documents are most useful?
- Which are retrieved but never cited?
- Which correlate with high-quality responses?

**Retrieval Mode Comparison:**
- BM25 vs. Vector vs. Hybrid performance
- Average response times by mode
- Quality scores by mode
- Best mode for each use case type

**Model Comparison:**
- Quality vs. speed vs. cost tradeoffs
- Average scores by model
- Token usage and costs
- Response time distributions

**Use Case Analysis:**
- Best settings for each use case
- Most common retrieval modes
- Average quality by use case

### Evaluation Tab

**Recent Query Runs:**
- View recent queries with metadata
- Quick evaluate any query
- Filter by collection or use case
- Sort by date or score

## API Reference

### Document Management

**Create Document**
```http
POST /api/documents
Content-Type: application/json

{
  "collection": "research",
  "title": "Document Title",
  "document_type": "article",
  "author": "Author Name",
  "year": 2024,
  "doi": "10.1234/example",
  "abstract": "Document abstract...",
  "notes": "Additional notes..."
}
```

**List Documents**
```http
GET /api/documents?collection=research&ingestion_status=complete&limit=100
```

**Get Document**
```http
GET /api/documents/{document_id}
```

**Update Document**
```http
PUT /api/documents/{document_id}
Content-Type: application/json

{
  "title": "Updated Title",
  "author": "Updated Author"
}
```

**Delete Document**
```http
DELETE /api/documents/{document_id}
```

### Query Tracking

**Create Query Run**
```http
POST /api/query-runs
Content-Type: application/json

{
  "user_query": "What is the impact of X?",
  "collection": "research",
  "session_id": "uuid",
  "retrieval_mode": "hybrid",
  "llm_model": "gpt-4",
  "use_case_type": "literature_review"
}
```

**List Query Runs**
```http
GET /api/query-runs?collection=research&limit=50
```

**Get Query Run**
```http
GET /api/query-runs/{query_run_id}
```

### Evaluation

**Create Evaluation**
```http
POST /api/evaluations
Content-Type: application/json

{
  "query_run_id": "uuid",
  "overall_score": 4,
  "accuracy_score": 5,
  "relevance_score": 4,
  "completeness_score": 3,
  "hallucination_flag": false,
  "feedback_text": "Good response but could be more complete"
}
```

**Get Evaluation**
```http
GET /api/evaluations/{evaluation_id}
```

### Analytics

**Document Analytics**
```http
GET /api/analytics/documents?collection=research
```

**Retrieval Mode Analytics**
```http
GET /api/analytics/retrieval-modes?collection=research
```

**Model Comparison**
```http
GET /api/analytics/models?collection=research
```

**Dashboard Summary**
```http
GET /api/analytics/dashboard?collection=research
```

## Database Schema

### Extended Documents Table

```sql
Documents (
  id BIGSERIAL PRIMARY KEY,
  collection TEXT,
  doc_id TEXT,
  filename TEXT,
  file_path TEXT,
  
  -- New fields
  document_type TEXT,
  author TEXT,
  year INTEGER,
  doi TEXT,
  source_type TEXT,
  pdf_attached BOOLEAN,
  ingestion_status TEXT,
  ingested_at TIMESTAMPTZ,
  chunk_count INTEGER,
  embedding_model TEXT,
  metadata_complete BOOLEAN,
  processing_error TEXT,
  needs_review BOOLEAN,
  last_queried_at TIMESTAMPTZ,
  times_retrieved INTEGER,
  times_cited INTEGER,
  is_active BOOLEAN,
  project_id UUID,
  user_id TEXT,
  
  -- Existing fields
  title TEXT,
  authors TEXT,
  abstract TEXT,
  notes TEXT,
  tags JSONB,
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ
)
```

### QueryRuns Table

```sql
QueryRuns (
  id UUID PRIMARY KEY,
  user_id TEXT,
  project_id UUID,
  session_id UUID,
  message_id UUID,
  
  user_query TEXT,
  final_response TEXT,
  collection TEXT,
  
  retrieval_mode TEXT,
  retrieval_profile TEXT,
  top_k INTEGER,
  top_k_sent_to_llm INTEGER,
  reranker_used BOOLEAN,
  reranker_model TEXT,
  
  llm_model TEXT,
  embedding_model TEXT,
  temperature REAL,
  prompt_template_version TEXT,
  
  response_time_ms REAL,
  retrieval_time_ms REAL,
  llm_time_ms REAL,
  token_input INTEGER,
  token_output INTEGER,
  estimated_cost REAL,
  
  use_case_type TEXT,
  metadata_filters_used JSONB,
  run_config_json JSONB,
  
  created_at TIMESTAMPTZ
)
```

### QueryRunDocuments Table

```sql
QueryRunDocuments (
  id UUID PRIMARY KEY,
  query_run_id UUID,
  document_id BIGINT,
  chunk_id BIGINT,
  
  retrieval_rank INTEGER,
  retrieval_score REAL,
  retrieval_source TEXT,
  rerank_score REAL,
  
  was_retrieved BOOLEAN,
  was_in_context BOOLEAN,
  was_cited BOOLEAN,
  
  contribution_type TEXT,
  created_at TIMESTAMPTZ
)
```

### QueryRunEvaluations Table

```sql
QueryRunEvaluations (
  id UUID PRIMARY KEY,
  query_run_id UUID,
  evaluator_user_id TEXT,
  
  overall_score INTEGER (1-5),
  accuracy_score INTEGER (1-5),
  relevance_score INTEGER (1-5),
  completeness_score INTEGER (1-5),
  clarity_score INTEGER (1-5),
  source_usefulness_score INTEGER (1-5),
  citation_quality_score INTEGER (1-5),
  
  hallucination_flag BOOLEAN,
  response_preference TEXT,
  feedback_text TEXT,
  
  created_at TIMESTAMPTZ
)
```

## Key Questions You Can Now Answer

### Document Operations

✅ **Which documents are incomplete or missing PDFs?**
- Filter by `pdf_attached = false` or `metadata_complete = false`

✅ **Which documents failed ingestion and why?**
- Filter by `ingestion_status = 'failed'`
- Check `processing_error` field
- View ingestion job history

✅ **Which documents have never been used?**
- Filter by `times_retrieved = 0`

### Retrieval Quality

✅ **Which documents are most useful?**
- Sort by `times_cited` or `avg_overall_score`
- View "Most Cited" ranking

✅ **Which retrieval modes work best for different query types?**
- Analytics → Retrieval Mode Performance
- Filter by `use_case_type`

✅ **Which documents are retrieved often but contribute poorly?**
- View "Retrieved but Not Cited" list
- Check documents with high `times_retrieved` but low `times_cited`

### Answer Quality

✅ **Which LLM models provide best quality/speed/cost balance?**
- Analytics → Model Comparison
- Compare avg scores, response times, and costs

✅ **Which settings optimize for specific use cases?**
- Analytics → Use Case Analysis
- See best retrieval modes per use case

✅ **How does reranking impact quality?**
- Compare query runs with `reranker_used = true` vs `false`
- Check average scores

✅ **Which documents correlate with high-quality responses?**
- Join QueryRunDocuments with QueryRunEvaluations
- Find documents in high-scoring query runs

## Maintenance

### Refresh Performance Summary

The materialized view should be refreshed periodically:

```sql
REFRESH MATERIALIZED VIEW CONCURRENTLY "DocumentPerformanceSummary";
```

Or via API:
```http
POST /api/documents/refresh-performance
```

### Cleanup Old Data

Optional retention policy for query runs:

```sql
-- Delete query runs older than 90 days
DELETE FROM "QueryRuns" 
WHERE created_at < NOW() - INTERVAL '90 days';
```

### Backup Important Evaluations

Export evaluations before cleanup:

```sql
COPY (
  SELECT * FROM "QueryRunEvaluations" 
  WHERE created_at > NOW() - INTERVAL '30 days'
) TO '/path/to/evaluations_backup.csv' CSV HEADER;
```

## Troubleshooting

### Documents not appearing in dashboard

- Check `is_active = true`
- Verify `user_id` matches (default: 'default_user')
- Check collection filter

### Query runs not being created

- Verify Supabase connection
- Check `query_tracker` is initialized
- Review server logs for errors

### Analytics showing no data

- Ensure query runs exist
- Refresh materialized view
- Check collection filter

### Ingestion jobs stuck in "processing"

- Check for crashed processes
- Review job error messages
- Manually update status if needed

## Best Practices

1. **Evaluate regularly** - Rate responses while context is fresh
2. **Tag use cases** - Helps identify optimal settings per scenario
3. **Monitor failed ingestions** - Address errors promptly
4. **Complete metadata** - Better metadata = better analytics
5. **Review unused documents** - Archive or improve low-performing docs
6. **Track experiments** - Use notes field to document configuration changes
7. **Refresh analytics** - Refresh materialized view daily or weekly

## Next Steps

1. Run the database migration
2. Upload some documents and test both workflows
3. Make some queries and evaluate responses
4. Explore the analytics dashboard
5. Identify optimization opportunities
6. Iterate and improve!

---

**Need Help?** Check the API reference or review the implementation files:
- `src/document_manager.py` - Document operations
- `src/query_tracker.py` - Query tracking
- `src/evaluation_manager.py` - Evaluation system
- `src/analytics_manager.py` - Analytics
