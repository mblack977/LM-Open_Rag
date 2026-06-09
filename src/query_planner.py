import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class QueryPlan:
    intent: str
    scope: str
    use_metadata: bool
    use_abstracts: bool
    use_chunks: bool
    chunk_strategy: str
    preferred_sections: List[str]
    avoid_sections: List[str]
    response_format: str
    minimum_documents: int
    search_terms: List[str]
    citations_required: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class QueryPlanner:
    """
    Classifies user queries and creates retrieval plans.
    Determines whether to use metadata, abstracts, or chunks based on query intent.
    """
    
    CONCEPT_KEYWORDS = [
        "what is", "what are", "define", "definition", "explain", "describe",
        "concept of", "meaning of", "refers to", "understood as"
    ]
    
    SYNTHESIS_KEYWORDS = [
        "main findings", "key findings", "what does the literature",
        "across these studies", "across the collection", "overall",
        "literature review", "research shows", "studies suggest"
    ]
    
    COMPARISON_KEYWORDS = [
        "compare", "contrast", "difference between", "similarities",
        "versus", "vs", "compared to"
    ]
    
    EVIDENCE_KEYWORDS = [
        "evidence for", "support for", "research on", "studies about",
        "findings about", "data on", "results for"
    ]
    
    FACTUAL_KEYWORDS = [
        "who wrote", "who is the author", "when was", "what year",
        "how many", "which article", "title of"
    ]
    
    def __init__(self, llm_client=None):
        self._llm_client = llm_client
    
    async def classify_query(self, query_text: str, collection: str) -> QueryPlan:
        """Classify a user query using LLM when available, keyword matching as fallback."""
        if self._llm_client is not None:
            try:
                plan = await self._classify_with_llm(query_text, collection)
                if plan is not None:
                    logger.info(f"LLM classified query as: {plan.intent}")
                    return plan
            except Exception as e:
                logger.warning(f"LLM query classification failed, using keyword fallback: {e}")
        return self._classify_with_keywords(query_text, collection)

    async def _classify_with_llm(self, query_text: str, collection: str) -> Optional[QueryPlan]:
        """Use the LLM to classify intent and expand search terms. Returns None on failure."""
        system_prompt = (
            "You are a query classifier. Output valid JSON only. "
            "No markdown, no code fences, no explanation — just the JSON object."
        )
        user_prompt = f"""Classify this research query and extract search terms.

Query: "{query_text}"

Return JSON with these exact keys:
{{
  "intent": "<one of: concept_explanation | research_synthesis | comparison | evidence_lookup | factual_lookup | general_question>",
  "search_terms": ["3 to 8 key terms and synonyms that capture the query's meaning"],
  "expanded_query": "<rewrite the query to be more search-optimised while preserving its meaning>"
}}

Intent definitions:
- concept_explanation: asks what something is, to define or explain a concept
- research_synthesis: asks for overall findings, patterns, or themes across literature
- comparison: asks to compare, contrast, or identify differences between things
- evidence_lookup: asks for evidence or research that supports a claim
- factual_lookup: asks a narrow factual question (who wrote, when, how many, which article)
- general_question: any other research question"""

        response = await self._llm_client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=256,
        )

        json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
        if not json_match:
            raise ValueError(f"No JSON in LLM response: {response[:200]}")

        data = json.loads(json_match.group())

        intent = str(data.get("intent", "general_question")).strip()
        raw_terms = data.get("search_terms", [])
        expanded_query = str(data.get("expanded_query", query_text)).strip()

        if not isinstance(raw_terms, list):
            raw_terms = []

        all_terms = [query_text, expanded_query] + [str(t) for t in raw_terms if t]
        seen: set = set()
        search_terms: List[str] = []
        for t in all_terms:
            t = t.strip()
            if t and t not in seen and len(t) > 1:
                seen.add(t)
                search_terms.append(t)
        search_terms = search_terms[:12]

        plan_fn = {
            "concept_explanation": self._plan_concept_explanation,
            "research_synthesis": self._plan_research_synthesis,
            "comparison": self._plan_comparison,
            "evidence_lookup": self._plan_evidence_lookup,
            "factual_lookup": self._plan_factual_lookup,
        }.get(intent, self._plan_default)

        plan = plan_fn(query_text, collection)
        plan.search_terms = search_terms
        return plan

    def _classify_with_keywords(self, query_text: str, collection: str) -> QueryPlan:
        """Keyword-based intent classification (fallback when LLM is unavailable)."""
        query_lower = query_text.lower().strip()
        intent = self._detect_intent(query_lower)

        if intent == "concept_explanation":
            return self._plan_concept_explanation(query_text, collection)
        elif intent == "research_synthesis":
            return self._plan_research_synthesis(query_text, collection)
        elif intent == "comparison":
            return self._plan_comparison(query_text, collection)
        elif intent == "evidence_lookup":
            return self._plan_evidence_lookup(query_text, collection)
        elif intent == "factual_lookup":
            return self._plan_factual_lookup(query_text, collection)
        else:
            return self._plan_default(query_text, collection)
    
    def _detect_intent(self, query_lower: str) -> str:
        """Detect the primary intent of the query."""
        if any(kw in query_lower for kw in self.FACTUAL_KEYWORDS):
            return "factual_lookup"
        if any(kw in query_lower for kw in self.CONCEPT_KEYWORDS):
            return "concept_explanation"
        if any(kw in query_lower for kw in self.SYNTHESIS_KEYWORDS):
            return "research_synthesis"
        if any(kw in query_lower for kw in self.COMPARISON_KEYWORDS):
            return "comparison"
        if any(kw in query_lower for kw in self.EVIDENCE_KEYWORDS):
            return "evidence_lookup"
        return "general_question"
    
    def _detect_scope(self, query_lower: str, query_text: str) -> str:
        """Detect whether the query is about a single document or the collection."""
        single_doc_indicators = [
            "this article", "this paper", "this study", "the article",
            "the paper", "the study", "in this document"
        ]
        
        collection_indicators = [
            "across", "collection", "literature", "studies", "articles",
            "research", "overall", "generally"
        ]
        
        if any(ind in query_lower for ind in single_doc_indicators):
            return "single_document"
        if any(ind in query_lower for ind in collection_indicators):
            return "collection"
        
        # Default to collection for broad questions
        return "collection"
    
    def _extract_search_terms(self, query_text: str) -> List[str]:
        """Extract key search terms from the query."""
        # Remove common question words
        stop_words = {
            "what", "is", "are", "the", "a", "an", "how", "why", "when",
            "where", "who", "which", "does", "do", "can", "could", "would",
            "should", "in", "on", "at", "to", "for", "of", "with", "from"
        }
        
        words = query_text.lower().split()
        terms = [w.strip("?.,!;:") for w in words if w.strip("?.,!;:") not in stop_words]
        
        # Also include the full query as a search term
        search_terms = [query_text]
        
        # Add bigrams and trigrams for key concepts
        for i in range(len(terms)):
            if i + 1 < len(terms):
                search_terms.append(f"{terms[i]} {terms[i+1]}")
            if i + 2 < len(terms):
                search_terms.append(f"{terms[i]} {terms[i+1]} {terms[i+2]}")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_terms = []
        for term in search_terms:
            if term not in seen and len(term) > 2:
                seen.add(term)
                unique_terms.append(term)
        
        return unique_terms[:10]  # Limit to top 10 terms
    
    def _plan_concept_explanation(self, query_text: str, collection: str) -> QueryPlan:
        """Plan for concept explanation queries."""
        return QueryPlan(
            intent="concept_explanation",
            scope="collection",
            use_metadata=True,
            use_abstracts=True,
            use_chunks=True,
            chunk_strategy="broad_concept_sampling",
            preferred_sections=[
                "abstract", "introduction", "theoretical framework",
                "literature review", "theory", "discussion", "conclusion"
            ],
            avoid_sections=[
                "references", "copyright", "publisher note", "appendix",
                "acknowledgments", "funding"
            ],
            response_format="definition_plus_collection_synthesis",
            minimum_documents=5,
            search_terms=self._extract_search_terms(query_text),
            citations_required=True
        )
    
    def _plan_research_synthesis(self, query_text: str, collection: str) -> QueryPlan:
        """Plan for research synthesis queries."""
        return QueryPlan(
            intent="research_synthesis",
            scope="collection",
            use_metadata=True,
            use_abstracts=True,
            use_chunks=True,
            chunk_strategy="findings_focused",
            preferred_sections=[
                "abstract", "results", "findings", "discussion",
                "conclusion", "implications"
            ],
            avoid_sections=[
                "references", "copyright", "publisher note", "appendix",
                "method", "methodology", "participants"
            ],
            response_format="synthesis_with_evidence",
            minimum_documents=8,
            search_terms=self._extract_search_terms(query_text),
            citations_required=True
        )
    
    def _plan_comparison(self, query_text: str, collection: str) -> QueryPlan:
        """Plan for comparison queries."""
        return QueryPlan(
            intent="comparison",
            scope="collection",
            use_metadata=True,
            use_abstracts=True,
            use_chunks=True,
            chunk_strategy="comparative_analysis",
            preferred_sections=[
                "abstract", "introduction", "literature review",
                "discussion", "conclusion"
            ],
            avoid_sections=[
                "references", "copyright", "publisher note", "appendix"
            ],
            response_format="comparative_synthesis",
            minimum_documents=4,
            search_terms=self._extract_search_terms(query_text),
            citations_required=True
        )
    
    def _plan_evidence_lookup(self, query_text: str, collection: str) -> QueryPlan:
        """Plan for evidence lookup queries."""
        return QueryPlan(
            intent="evidence_lookup",
            scope="collection",
            use_metadata=True,
            use_abstracts=True,
            use_chunks=True,
            chunk_strategy="evidence_focused",
            preferred_sections=[
                "abstract", "results", "findings", "discussion"
            ],
            avoid_sections=[
                "references", "copyright", "publisher note", "appendix"
            ],
            response_format="evidence_summary",
            minimum_documents=5,
            search_terms=self._extract_search_terms(query_text),
            citations_required=True
        )
    
    def _plan_factual_lookup(self, query_text: str, collection: str) -> QueryPlan:
        """Plan for simple factual queries."""
        return QueryPlan(
            intent="factual_lookup",
            scope="single_document",
            use_metadata=True,
            use_abstracts=False,
            use_chunks=False,
            chunk_strategy="metadata_only",
            preferred_sections=[],
            avoid_sections=[],
            response_format="direct_answer",
            minimum_documents=1,
            search_terms=self._extract_search_terms(query_text),
            citations_required=False
        )
    
    def _plan_default(self, query_text: str, collection: str) -> QueryPlan:
        """Default plan for general questions."""
        return QueryPlan(
            intent="general_question",
            scope="collection",
            use_metadata=True,
            use_abstracts=True,
            use_chunks=True,
            chunk_strategy="balanced",
            preferred_sections=[
                "abstract", "introduction", "discussion", "conclusion"
            ],
            avoid_sections=[
                "references", "copyright", "publisher note", "appendix"
            ],
            response_format="comprehensive_answer",
            minimum_documents=5,
            search_terms=self._extract_search_terms(query_text),
            citations_required=True
        )
