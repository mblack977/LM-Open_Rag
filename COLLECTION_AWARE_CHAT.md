# Collection-Aware Chat System

## Overview

The collection-aware chat system transforms your RAG from a **chunk responder** into a **collection-aware research assistant**. Instead of retrieving a few chunks and generating narrow answers, it:

1. **Classifies the query** by intent and scope
2. **Searches document metadata** to identify relevant articles
3. **Retrieves targeted evidence** from abstracts and specific sections
4. **Synthesizes across the collection** using appropriate response templates

## The Problem It Solves

### Before (Chunk Responder)
```
User: "What is academic self-concept?"

System:
1. Embeds query
2. Retrieves top 3-5 chunks
3. Generates answer from those chunks only

Result: "Academic self-concept refers to... Key details from the context 
include effect sizes of .51..." (narrow, disconnected answer)
```

### After (Collection-Aware Research Assistant)
```
User: "What is academic self-concept?"

System:
1. Classifies as "concept_explanation" with "collection" scope
2. Searches 20 articles for mentions of academic self-concept
3. Identifies 12 relevant articles
4. Retrieves abstracts + targeted chunks from introduction, theory, discussion
5. Generates structured synthesis across the collection

Result: Comprehensive 400-600 word explanation covering:
- Clear definition
- How the concept is understood across the collection
- Important distinctions from related concepts
- Why it matters
- What the research collectively suggests
```

## Architecture

### Three-Stage Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│ Stage 1: Query Classification (QueryPlanner)               │
├─────────────────────────────────────────────────────────────┤
│ Input: "What is academic self-concept?"                     │
│ Output: QueryPlan {                                         │
│   intent: "concept_explanation"                             │
│   scope: "collection"                                       │
│   minimum_documents: 5                                      │
│   preferred_sections: ["abstract", "introduction", ...]     │
│   response_format: "definition_plus_collection_synthesis"   │
│ }                                                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Stage 2: Multi-Stage Retrieval (CollectionRetriever)       │
├─────────────────────────────────────────────────────────────┤
│ 2a. Search Documents table (metadata + abstracts)           │
│     → Score by relevance to search terms                    │
│     → Return top 10-20 candidate documents                  │
│                                                              │
│ 2b. Retrieve targeted chunks from candidates                │
│     → Use vector search within each document                │
│     → Filter by preferred sections                          │
│     → Return 25-30 chunks across multiple documents         │
│                                                              │
│ Output: EvidencePack {                                      │
│   candidate_documents: [12 documents]                       │
│   chunks: [28 chunks from 10 documents]                     │
│   total_documents_searched: 20                              │
│ }                                                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Stage 3: Response Generation (ResponseGenerator)           │
├─────────────────────────────────────────────────────────────┤
│ Uses intent-specific template:                              │
│ - Concept Explanation: Definition → Understanding →         │
│   Distinctions → Implications → Synthesis                   │
│ - Research Synthesis: Overview → Key Findings →             │
│   Patterns → Implications                                   │
│ - Comparison: Overview → Similarities → Differences →       │
│   Relationships                                              │
│                                                              │
│ Output: Comprehensive, structured answer (400-600 words)    │
└─────────────────────────────────────────────────────────────┘
```

## Query Intent Types

The system recognizes six query intents:

### 1. Concept Explanation
**Triggers:** "what is", "define", "explain", "describe", "concept of"

**Example:** "What is academic self-concept?"

**Behavior:**
- Searches across collection for concept mentions
- Retrieves from: abstract, introduction, theory, literature review, discussion
- Minimum 5 documents
- Response format: Definition → Collection understanding → Distinctions → Implications

### 2. Research Synthesis
**Triggers:** "main findings", "what does the literature", "across these studies", "overall"

**Example:** "What are the main findings about academic self-concept and achievement?"

**Behavior:**
- Searches for empirical findings
- Retrieves from: abstract, results, findings, discussion, conclusion
- Minimum 8 documents
- Response format: Overview → Key findings → Patterns → Implications

### 3. Comparison
**Triggers:** "compare", "contrast", "difference between", "similarities", "versus"

**Example:** "Compare academic self-concept and self-efficacy"

**Behavior:**
- Searches for both concepts
- Retrieves from: abstract, introduction, literature review, discussion
- Minimum 4 documents
- Response format: Overview → Similarities → Differences → Relationships

### 4. Evidence Lookup
**Triggers:** "evidence for", "research on", "studies about", "findings about"

**Example:** "What evidence exists for the big-fish-little-pond effect?"

**Behavior:**
- Searches for empirical evidence
- Retrieves from: abstract, results, findings, discussion
- Minimum 5 documents
- Response format: Evidence summary with specific findings

### 5. Factual Lookup
**Triggers:** "who wrote", "when was", "what year", "how many articles"

**Example:** "Who wrote this article?"

**Behavior:**
- Uses metadata only (no chunks)
- Direct, concise answer (1-3 sentences)
- Minimum 1 document

### 6. General Question
**Default for queries that don't match above patterns**

**Behavior:**
- Balanced retrieval across sections
- Minimum 5 documents
- Comprehensive answer format

## Usage

### Option 1: Enable Globally via Environment Variable

Add to your `.env` file:
```bash
USE_COLLECTION_AWARE_CHAT=true
```

All requests to `/v1/chat/completions` will use collection-aware mode.

### Option 2: Enable Per-Request

Send `collection_aware: true` in the request payload:

```python
import requests

response = requests.post(
    "http://localhost:8000/v1/chat/completions",
    json={
        "model": "rag-herb_collection",
        "messages": [
            {"role": "user", "content": "What is academic self-concept?"}
        ],
        "collection_aware": True  # Enable collection-aware mode
    }
)
```

### Option 3: Use Dedicated Endpoint

Use the dedicated collection-aware endpoint:

```python
response = requests.post(
    "http://localhost:8000/v1/chat/completions/collection-aware",
    json={
        "model": "rag-herb_collection",
        "messages": [
            {"role": "user", "content": "What is academic self-concept?"}
        ]
    }
)
```

## Response Metadata

Collection-aware responses include rich metadata:

```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "rag-herb_collection",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "Academic self-concept refers to..."
    },
    "finish_reason": "stop"
  }],
  "metadata": {
    "query_intent": "concept_explanation",
    "query_scope": "collection",
    "documents_searched": 20,
    "documents_used": 12,
    "chunks_used": 28,
    "response_type": "concept_explanation",
    "retrieval_time_ms": 450,
    "llm_time_ms": 3200,
    "total_time_ms": 3650
  }
}
```

## Example Queries and Expected Behavior

### Concept Explanation
```
Q: "What is academic self-concept?"
Intent: concept_explanation
Documents: 12 from collection of 20
Chunks: 28 from abstracts, introductions, theory sections
Response: 450-word structured explanation
```

### Research Synthesis
```
Q: "What does the literature say about the relationship between 
    academic self-concept and achievement?"
Intent: research_synthesis
Documents: 15 from collection of 20
Chunks: 30 from results and discussion sections
Response: 500-word synthesis of findings with patterns
```

### Comparison
```
Q: "What is the difference between academic self-concept and 
    self-efficacy?"
Intent: comparison
Documents: 8 from collection of 20
Chunks: 24 from theoretical and discussion sections
Response: 400-word comparative analysis
```

### Evidence Lookup
```
Q: "What evidence supports the big-fish-little-pond effect?"
Intent: evidence_lookup
Documents: 10 from collection of 20
Chunks: 25 from results sections
Response: 350-word evidence summary with specific findings
```

## Configuration

### Environment Variables

```bash
# Enable collection-aware chat globally
USE_COLLECTION_AWARE_CHAT=true

# LLM settings (affects response quality)
LM_STUDIO_BASE_URL=http://localhost:1234/v1
LM_STUDIO_API_KEY=lm-studio

# Embedding settings (affects retrieval)
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

### Customizing Query Classification

Edit `src/query_planner.py` to add custom keywords or modify intent detection:

```python
CONCEPT_KEYWORDS = [
    "what is", "what are", "define", "definition", 
    "explain", "describe", "concept of", "meaning of"
    # Add your custom keywords here
]
```

### Customizing Response Templates

Edit `src/response_generator.py` to modify response structures:

```python
async def _generate_concept_explanation(self, evidence_pack: EvidencePack):
    # Customize the prompt template here
    user_prompt = f"""
    Your custom instructions...
    """
```

## Key Differences from Traditional RAG

| Aspect | Traditional RAG | Collection-Aware |
|--------|----------------|------------------|
| **Retrieval** | Top K chunks only | Metadata → Documents → Targeted chunks |
| **Scope** | Narrow (3-5 chunks) | Broad (5-20 documents, 25-30 chunks) |
| **Context** | Single retrieval step | Multi-stage with document identification |
| **Response** | Generic template | Intent-specific templates |
| **Sources** | Random chunks | Preferred sections (abstract, intro, theory) |
| **Synthesis** | Minimal | Explicit cross-document synthesis |
| **Answer length** | 100-200 words | 400-600 words |
| **Quality** | Narrow, disconnected | Comprehensive, structured |

## Performance Considerations

### Retrieval Time
- Traditional: 200-400ms
- Collection-aware: 400-800ms (worth it for quality)

### LLM Time
- Traditional: 1000-2000ms (shorter prompts)
- Collection-aware: 2500-4000ms (longer, structured prompts)

### Total Time
- Traditional: ~1.5-2.5 seconds
- Collection-aware: ~3-5 seconds

**Trade-off:** Slightly slower, but dramatically better answers.

## Troubleshooting

### "Collection-aware chat requires Supabase"
**Solution:** Ensure Supabase is configured in `.env`:
```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
```

### Answers are still too short
**Check:**
1. Is collection-aware mode actually enabled? Check logs for "Using collection-aware chat mode"
2. Are documents in the Documents table? Query: `SELECT COUNT(*) FROM "Documents"`
3. Are abstracts populated? Query: `SELECT COUNT(*) FROM "Documents" WHERE abstract IS NOT NULL`

### No documents found
**Solution:** Ensure documents have metadata in the Documents table. Run document ingestion with metadata extraction enabled.

### Wrong intent detected
**Solution:** Add custom keywords to `QueryPlanner` or use more specific query phrasing.

## Future Enhancements

Potential improvements:

1. **LLM-based intent classification** - Use LLM to classify complex queries
2. **Citation extraction** - Extract and format proper citations
3. **Multi-turn context** - Maintain conversation context across turns
4. **Custom retrieval profiles** - Per-collection retrieval strategies
5. **Adaptive chunk selection** - Learn which sections are most useful
6. **Answer quality scoring** - Automatic evaluation of response quality

## Contributing

To extend the system:

1. **Add new intent types** - Edit `QueryPlanner.classify_query()`
2. **Add new response templates** - Add methods to `ResponseGenerator`
3. **Customize section filtering** - Edit `CollectionRetriever._should_include_chunk()`
4. **Adjust scoring** - Modify `CollectionRetriever._score_document_relevance()`

## License

Same as parent project.
