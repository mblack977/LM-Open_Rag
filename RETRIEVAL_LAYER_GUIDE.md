# Retrieval Layer System Guide

## Overview

The retrieval layer has been redesigned as a **first-class, user-selectable feature** rather than a hidden backend choice. This system supports multiple retrieval modes, allows users to choose retrieval profiles for each project, and provides comprehensive benchmarking and optimization capabilities.

## Architecture

### Three-Layer User Experience

#### 1. Simple Profile Selector (Layer 1)
Ordinary users can choose from predefined retrieval profiles without understanding ranking internals:

- **Keyword Heavy**: Prioritizes exact keyword matching (BM25: 50%, FTS: 30%, Vector: 20%)
- **Balanced**: General-purpose balanced approach (BM25: 30%, FTS: 20%, Vector: 50%)
- **Conceptual**: Emphasizes semantic similarity (BM25: 10%, FTS: 10%, Vector: 80%)
- **Academic Evidence**: Optimized for research findings (BM25: 25%, FTS: 25%, Vector: 50%)
- **Custom**: User-defined weights

#### 2. Advanced Tuning Panel (Layer 2)
Power users can fine-tune retrieval settings:

- BM25 weight (0.0 - 1.0)
- PostgreSQL FTS weight (0.0 - 1.0)
- Vector search weight (0.0 - 1.0)
- Reranker on/off
- Score normalization on/off
- Metadata filter boost
- Citation graph boost (placeholder for future)
- Save custom profiles

#### 3. Evaluation Dashboard (Layer 3)
View benchmark-driven optimization results:

- Benchmark set used
- Retrieval methods tested
- Best learned profile
- Improvement over baseline
- Metrics: Precision@5/10, Recall@5/10/20, NDCG@5/10, MRR, MAP

## Retrieval Methods

### Supported Retrieval Strategies

1. **BM25 Keyword Retrieval**: Traditional term-based ranking with TF-IDF weighting
2. **PostgreSQL Full-Text Search (FTS)**: Database-native text search with ranking
3. **Dense Vector Retrieval**: Semantic similarity using embeddings
4. **Weighted Hybrid Retrieval**: Combines all methods with configurable weights
5. **Hybrid with Reranking**: Applies reranking model to hybrid results

### Hybrid Retrieval Engine

The `HybridRetrievalEngine` merges results from multiple sources:

```python
# Score normalization (MinMax or Z-score)
# Weighted combination based on profile
final_score = (bm25_score * bm25_weight) + 
              (fts_score * fts_weight) + 
              (vec_score * vec_weight)
```

Alternative: Reciprocal Rank Fusion (RRF)
```python
rrf_score = sum(1 / (k + rank_i + 1)) for all sources
```

## Benchmark System

### Benchmark Query Structure

```python
{
  "query_id": "unique_id",
  "collection": "project_name",
  "query_text": "What is academic self-concept?",
  "query_type": "definitional",  # or empirical_evidence, critique, methodological, synthesis
  "section_goal": "background",   # or literature_review, methodology
  "difficulty": "medium",         # easy, medium, hard
  "source": "hand_curated",       # or user_interaction, section_heading
  "notes": "Optional notes"
}
```

### Query Types for Academic Use

- **Definitional**: "What is X?", "Define Y"
- **Empirical Evidence**: "What research shows...", "What are the findings..."
- **Critique**: "What are the limitations...", "What problems exist..."
- **Methodological**: "How to measure...", "What methods..."
- **Synthesis**: "How do these relate...", "What is the overall picture..."

### Relevance Labeling

Three levels of annotation:

#### 1. Document-Level Relevance
- `highly_relevant`: Core document for answering the query
- `somewhat_relevant`: Provides context or partial answer
- `not_relevant`: Not useful for this query

#### 2. Chunk-Level Relevance
- `supporting_evidence`: Directly answers the query
- `background_only`: Provides context but not the answer
- `not_relevant`: Not useful

#### 3. Evidence Role Labeling
For literature review synthesis:
- `definition`: Defines a concept
- `background`: Background information
- `empirical_finding`: Research results
- `critique`: Critical analysis
- `method`: Methodology description
- `limitation`: Study limitations
- `gap`: Research gap identification

## Optimization System

### Grid Search Optimization

The system performs transparent grid search over weight combinations:

```python
# Default search space
bm25_range = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
fts_range = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
vec_range = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]

# Evaluates each combination against benchmark metrics
# Selects best performing configuration
```

### Evaluation Metrics

- **Precision@K**: Fraction of top-K results that are relevant
- **Recall@K**: Fraction of relevant documents found in top-K
- **NDCG@K**: Normalized Discounted Cumulative Gain (considers ranking quality)
- **MRR**: Mean Reciprocal Rank (position of first relevant result)
- **MAP**: Mean Average Precision (average precision across all queries)

### Per-Query-Type Optimization

Different query types can use different optimal profiles:

```python
# Example: Definitional queries may favor keyword matching
# Conceptual queries may favor semantic search
optimized_profiles = {
  "definitional": Profile(bm25=0.5, fts=0.3, vec=0.2),
  "empirical_evidence": Profile(bm25=0.25, fts=0.25, vec=0.5),
  "synthesis": Profile(bm25=0.1, fts=0.1, vec=0.8)
}
```

## Database Schema

### Core Tables

1. **RetrievalProfiles**: Store retrieval configurations
2. **ProjectRetrievalSettings**: Map projects to profiles
3. **BenchmarkQueries**: Evaluation query set
4. **BenchmarkRelevanceLabels**: Ground truth annotations
5. **RetrievalRuns**: Evaluation results
6. **RetrievalRunDetails**: Per-query results
7. **OptimizationHistory**: Grid search results
8. **AnnotationSessions**: Track annotation work

## API Endpoints

### Profile Management

```
GET    /retrieval/profiles                    # List all profiles
GET    /retrieval/profiles/{name}             # Get specific profile
POST   /retrieval/profiles                    # Create custom profile
PUT    /retrieval/profiles/{name}             # Update profile
DELETE /retrieval/profiles/{name}             # Delete custom profile

GET    /retrieval/projects/{collection}/profile    # Get project profile
PUT    /retrieval/projects/{collection}/profile    # Set project profile
```

### Benchmark Management

```
GET    /retrieval/benchmarks                  # List benchmark queries
POST   /retrieval/benchmarks                  # Create benchmark query
POST   /retrieval/benchmarks/bulk             # Bulk create queries

POST   /retrieval/labels                      # Create relevance label
POST   /retrieval/labels/bulk                 # Bulk create labels
GET    /retrieval/labels/{query_id}           # Get labels for query

POST   /retrieval/annotations/sessions        # Create annotation session
```

### Evaluation & Optimization

```
GET    /retrieval/runs                        # List evaluation runs
GET    /retrieval/runs/best                   # Get best run for collection
GET    /retrieval/optimizations               # List optimization history
```

## Usage Examples

### 1. Set Project Retrieval Profile

```python
# Use predefined profile
PUT /retrieval/projects/my_collection/profile
{
  "profile_name": "academic_evidence"
}

# Use custom weights
PUT /retrieval/projects/my_collection/profile
{
  "bm25_weight": 0.3,
  "fts_weight": 0.2,
  "vec_weight": 0.5,
  "use_reranker": false
}
```

### 2. Create Benchmark Set

```python
POST /retrieval/benchmarks/bulk
{
  "queries": [
    {
      "collection": "my_collection",
      "query_text": "What is academic self-concept?",
      "query_type": "definitional",
      "source": "hand_curated"
    },
    {
      "collection": "my_collection",
      "query_text": "What research supports the relationship between self-concept and achievement?",
      "query_type": "empirical_evidence",
      "source": "hand_curated"
    }
  ]
}
```

### 3. Annotate Relevance

```python
POST /retrieval/labels/bulk
{
  "labels": [
    {
      "query_id": "query_123",
      "collection": "my_collection",
      "doc_id": "doc_456",
      "doc_relevance": "highly_relevant",
      "chunk_index": 5,
      "chunk_relevance": "supporting_evidence",
      "evidence_role": "definition",
      "annotator": "researcher_1",
      "confidence": 1.0
    }
  ]
}
```

### 4. Run Optimization

```python
from src.retrieval_optimization import GridSearchOptimizer
from src.benchmark_manager import BenchmarkManager

# Load benchmark queries and labels
benchmark_mgr = BenchmarkManager(supabase)
queries = await benchmark_mgr.list_benchmark_queries(collection="my_collection")
labels_by_query = await benchmark_mgr.get_labels_by_collection("my_collection")

# Run grid search
optimizer = GridSearchOptimizer()
best_profile, best_metrics, all_results = optimizer.optimize_weights(
    retrieval_function=my_retrieval_fn,
    benchmark_queries=queries,
    labels_by_query=labels_by_query,
    metric_name="ndcg_at_10"
)

# Save best profile
await profile_manager.create_profile(best_profile)
await profile_manager.set_project_profile("my_collection", best_profile.profile_name)
```

## Practical First Release Workflow

### Step 1: Create Manual Profiles
- Define 4-5 retrieval profiles with different weight combinations
- Test manually on sample queries

### Step 2: Build Benchmark Set
- Create ~100 literature review queries covering:
  - 30% definitional queries
  - 30% empirical evidence queries
  - 20% methodological queries
  - 20% synthesis queries
- Sources: real user questions, hand-curated, section headings

### Step 3: Annotation Interface
- Simple web UI showing:
  - Query text
  - Top retrieved results from each method
  - Quick buttons for relevance labels
- Annotate 20-30 queries initially

### Step 4: Run Grid Search
- Test weight combinations on annotated queries
- Evaluate with Precision@5, Recall@10, NDCG@10
- Identify best performing profile

### Step 5: Evaluation Dashboard
- Show benchmark metrics
- Display best profile vs baseline
- One-click application to project
- Present as "Optimise retrieval profile from benchmark data"

## Future Enhancements

1. **Automatic Profile Selection**: Recommend profile based on query type
2. **Citation Graph Boost**: Leverage document citation relationships
3. **Learning to Rank**: ML-based reranking models
4. **Query Expansion**: Automatic query reformulation
5. **Feedback Loop**: Learn from user interactions
6. **A/B Testing**: Compare profiles in production
7. **Real-time Optimization**: Continuous learning from usage

## Files Created

### Core System
- `src/retrieval_profiles.py` - Profile definitions and built-in profiles
- `src/hybrid_retrieval.py` - Hybrid retrieval engine with score merging
- `src/retrieval_evaluation.py` - Evaluation metrics and benchmark queries
- `src/retrieval_optimization.py` - Grid search and optimization
- `src/retrieval_profile_manager.py` - Profile database operations
- `src/benchmark_manager.py` - Benchmark and annotation management
- `src/retrieval_api.py` - API layer for retrieval system

### Database
- `RETRIEVAL_SCHEMA.sql` - Complete database schema for retrieval layer

### Integration
- Updated `main.py` with retrieval API endpoints

## Next Steps

1. **Run Database Migration**: Execute `RETRIEVAL_SCHEMA.sql` in Supabase
2. **Build Frontend UI**: Create profile selector and tuning panel
3. **Create Initial Benchmarks**: Add 20-30 hand-curated queries
4. **Annotate Queries**: Label relevance for initial benchmark set
5. **Run First Optimization**: Execute grid search to find optimal weights
6. **Deploy Best Profile**: Apply optimized profile to production collection

## Support

The retrieval layer is designed to be:
- **Transparent**: Users see what retrieval method is being used
- **Auditable**: All optimization results are stored and explainable
- **Flexible**: Supports both simple and advanced use cases
- **Academic-focused**: Optimized for literature review and research tasks
