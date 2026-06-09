# Quick Start: Collection-Aware Chat

## What You Get

Transform your RAG from giving **narrow, disconnected answers** to providing **comprehensive, collection-level research syntheses**.

**Before:**
> "Academic self-concept refers to... Key details from the context include effect sizes of .51..." (120 words, from 3 chunks)

**After:**
> "Academic self-concept refers to a student's perception of their academic ability, competence, and effectiveness as a learner. Across this collection, the concept is treated not simply as general confidence, but as a domain-specific self-belief shaped by achievement, feedback, comparison with peers, and prior learning experiences..." (450 words, synthesized from 12 articles)

## 5-Minute Setup

### Step 1: Ensure Prerequisites

You need:
- ✅ Supabase configured (Documents table with metadata)
- ✅ Documents ingested with title, authors, abstract
- ✅ LM Studio or compatible LLM running

### Step 2: Enable Collection-Aware Mode

**Option A: Enable globally**

Add to `.env`:
```bash
USE_COLLECTION_AWARE_CHAT=true
```

**Option B: Enable per-request**

Add `"collection_aware": true` to your request:
```python
response = requests.post(
    "http://localhost:8000/v1/chat/completions",
    json={
        "model": "rag-your_collection",
        "messages": [{"role": "user", "content": "What is academic self-concept?"}],
        "collection_aware": True  # ← Add this
    }
)
```

### Step 3: Test It

Run the test script:
```bash
python test_collection_aware.py
```

Or test manually:
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "rag-your_collection",
    "messages": [{"role": "user", "content": "What is academic self-concept?"}],
    "collection_aware": true
  }'
```

## How It Works (Simple Version)

```
Your Question
    ↓
1. System classifies: "This is a concept explanation question"
    ↓
2. System searches: "Which articles discuss this concept?"
    → Finds 12 relevant articles from your collection
    ↓
3. System retrieves: "Get abstracts + key sections from these 12 articles"
    → Retrieves 28 chunks from introduction, theory, discussion sections
    ↓
4. System synthesizes: "Generate comprehensive explanation across all evidence"
    → Uses concept explanation template
    ↓
Your Answer (400-600 words, properly structured)
```

## Query Types Supported

### 1. Concept Questions
**Ask:** "What is [concept]?" or "Define [concept]"

**You get:** Comprehensive definition + how it's understood across your collection + distinctions + implications

**Example:**
```
Q: "What is academic self-concept?"
A: 450-word structured explanation synthesized from 12 articles
```

### 2. Research Synthesis
**Ask:** "What does the literature say about...?" or "What are the main findings...?"

**You get:** Overview + key findings + patterns + implications across studies

**Example:**
```
Q: "What are the main findings about academic self-concept and achievement?"
A: 500-word synthesis of findings with patterns identified
```

### 3. Comparisons
**Ask:** "What is the difference between X and Y?" or "Compare X and Y"

**You get:** Structured comparison with similarities, differences, and relationships

**Example:**
```
Q: "Compare academic self-concept and self-efficacy"
A: 400-word comparative analysis
```

### 4. Evidence Questions
**Ask:** "What evidence exists for...?" or "What research supports...?"

**You get:** Evidence summary with specific findings and results

**Example:**
```
Q: "What evidence supports the big-fish-little-pond effect?"
A: 350-word evidence summary with specific studies
```

## Checking It's Working

### Look for these signs:

**1. In the logs:**
```
INFO: Using collection-aware chat mode
INFO: Query classified as: concept_explanation (scope: collection)
INFO: Retrieved evidence from 12 documents, 28 chunks in 450ms
```

**2. In the response metadata:**
```json
{
  "metadata": {
    "query_intent": "concept_explanation",
    "documents_used": 12,
    "chunks_used": 28,
    "response_type": "concept_explanation"
  }
}
```

**3. In the answer quality:**
- ✅ 400-600 words (not 100-150)
- ✅ Structured with clear sections
- ✅ References "across the collection" or "these studies"
- ✅ Synthesizes rather than lists facts
- ✅ No random effect sizes without context

## Troubleshooting

### "Still getting short answers"

**Check:**
1. Is it actually enabled? Look for "Using collection-aware chat mode" in logs
2. Do your documents have metadata? Run: `SELECT COUNT(*) FROM "Documents" WHERE abstract IS NOT NULL`
3. Is Supabase connected? Check logs for Supabase initialization

### "No documents found"

**Solution:** Your Documents table needs metadata. Make sure you've ingested documents with:
- `title`
- `authors`
- `abstract`

### "Wrong intent detected"

**Solution:** The query classifier uses keyword matching. Try rephrasing:
- ❌ "Tell me about academic self-concept" → might be classified as general
- ✅ "What is academic self-concept?" → classified as concept_explanation

## Performance

Expect slightly slower responses (worth it for quality):

| Metric | Traditional | Collection-Aware |
|--------|-------------|------------------|
| Retrieval | 200-400ms | 400-800ms |
| LLM | 1000-2000ms | 2500-4000ms |
| **Total** | **~2s** | **~4s** |
| Answer length | 100-200 words | 400-600 words |
| Documents used | N/A | 5-15 |
| Quality | Narrow | Comprehensive |

## Next Steps

1. **Test with your collection:**
   ```bash
   python test_collection_aware.py
   ```

2. **Try different query types:**
   - Concept: "What is [your concept]?"
   - Synthesis: "What does the literature say about [topic]?"
   - Comparison: "Compare [concept A] and [concept B]"

3. **Customize for your domain:**
   - Edit `src/query_planner.py` to add domain-specific keywords
   - Edit `src/response_generator.py` to customize response templates

4. **Read full documentation:**
   - See `COLLECTION_AWARE_CHAT.md` for complete details

## Example Session

```python
import requests

BASE_URL = "http://localhost:8000"

# Test concept explanation
response = requests.post(
    f"{BASE_URL}/v1/chat/completions",
    json={
        "model": "rag-herb_collection",
        "messages": [
            {"role": "user", "content": "What is academic self-concept?"}
        ],
        "collection_aware": True
    }
)

result = response.json()
print(result["choices"][0]["message"]["content"])
print(f"\nUsed {result['metadata']['documents_used']} documents")
print(f"Intent: {result['metadata']['query_intent']}")
```

## Support

If you encounter issues:

1. Check logs for error messages
2. Verify Supabase connection
3. Ensure Documents table has metadata
4. See `COLLECTION_AWARE_CHAT.md` for detailed troubleshooting

## Key Takeaway

**The system now thinks:**
> "What kind of research task is the user asking me to perform, and what combination of abstracts, metadata, and chunks do I need to answer it well?"

**Instead of:**
> "What chunk answers this question?"

This is the difference between a **chunk responder** and a **research assistant**.
