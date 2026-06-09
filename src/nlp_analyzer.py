import re
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# --- spaCy optional import with lazy model loading ---
try:
    import spacy as _spacy_module
    _SPACY_IMPORTED = True
except ImportError:
    _SPACY_IMPORTED = False
    _spacy_module = None

_NLP_MODEL = None  # loaded on first use


def _get_nlp():
    global _NLP_MODEL
    if not _SPACY_IMPORTED:
        return None
    if _NLP_MODEL is None:
        try:
            _NLP_MODEL = _spacy_module.load("en_core_web_sm")
        except OSError:
            logger.warning(
                "spaCy model 'en_core_web_sm' not found — using keyword fallback. "
                "Install it with: python -m spacy download en_core_web_sm"
            )
            _NLP_MODEL = False
    return _NLP_MODEL if _NLP_MODEL is not False else None


# --- Regex patterns for question-type classification ---
_RE_SYNTHESIS = re.compile(
    r'\b(main findings?|key findings?|literature (says?|shows?|suggests?|indicates?)|'
    r'across (the )?(studies|articles|collection|literature|research)|'
    r'synthesize|synthesis|literature review|'
    r'research (shows?|suggests?|indicates?|finds?)|'
    r'what do .{0,20}(studies|researchers|articles) (say|show|suggest|find)|'
    r'trends? in|patterns? in|themes? in|overall findings?|common findings?)\b',
    re.I,
)
_RE_COMPARATIVE = re.compile(
    r'\b(compar|contrast|difference between|similarities? between|'
    r'versus|vs\.?|compared to|distinguish|how .{0,20}differ|'
    r'what.{0,20}differ|relationship between)\b',
    re.I,
)
_RE_ANALYTICAL = re.compile(
    r'\b(how does|why does|why is|why are|what causes?|what effect|what impact|'
    r'how can|how do|explain how|explain why|what role|what function|'
    r'mechanism|process of|what happens when|implications? of|consequences? of)\b',
    re.I,
)
_RE_DEFINITIONAL = re.compile(
    r'\b(what is|what are|define|definition of|explain what|meaning of|'
    r'refers? to|understood as|describe what|concept of)\b',
    re.I,
)
_RE_FACTUAL = re.compile(
    r'\b(who (is|was|wrote|authored|published)|when (was|did|is)|'
    r'how many|how much|which article|which paper|which study|'
    r'what year|what date|list of|name of|title of|'
    r'in what year|how old)\b',
    re.I,
)
_RE_MULTI_PART = re.compile(
    r'\b(and also|as well as|additionally|furthermore|in addition|'
    r'what about|another question|also (explain|describe|tell))\b',
    re.I,
)

# Base complexity by question type (0.0–1.0 scale)
_BASE_COMPLEXITY = {
    "factual":      0.10,
    "definitional": 0.35,
    "analytical":   0.55,
    "comparative":  0.65,
    "synthesis":    0.75,
    "unknown":      0.40,
}


@dataclass
class QueryAnalysis:
    question_type: str       # factual | definitional | analytical | comparative | synthesis | unknown
    complexity_score: float  # 0.0 (simple/fast) → 1.0 (complex/thinking)
    entities: List[Dict]     # [{text, label}, ...] — populated when spaCy available
    sentence_count: int
    is_multi_part: bool
    features: Dict           # raw breakdown for response metadata


def _detect_question_type(text: str) -> str:
    if _RE_SYNTHESIS.search(text):
        return "synthesis"
    if _RE_COMPARATIVE.search(text):
        return "comparative"
    if _RE_ANALYTICAL.search(text):
        return "analytical"
    if _RE_DEFINITIONAL.search(text):
        return "definitional"
    if _RE_FACTUAL.search(text):
        return "factual"
    return "unknown"


def _tree_depth(token) -> int:
    depth = 0
    while token.head != token:
        token = token.head
        depth += 1
    return depth


_SUB_CLAUSE_DEPS = {"advcl", "relcl", "ccomp", "xcomp", "acl"}


def _analyze_with_spacy(text: str, nlp) -> QueryAnalysis:
    doc = nlp(text)

    entities = [{"text": ent.text, "label": ent.label_} for ent in doc.ents]
    sentences = list(doc.sents)
    sentence_count = len(sentences)
    max_depth = max((_tree_depth(t) for t in doc), default=0)
    sub_clauses = sum(1 for t in doc if t.dep_ in _SUB_CLAUSE_DEPS)
    is_multi_part = bool(_RE_MULTI_PART.search(text)) or sub_clauses >= 2

    question_type = _detect_question_type(text)
    score = _BASE_COMPLEXITY[question_type]
    score += min(0.12, (sentence_count - 1) * 0.05)   # multi-sentence
    score += min(0.12, sub_clauses * 0.04)              # subordinate clauses
    score += min(0.10, max(0, len(entities) - 1) * 0.03)  # entity richness
    score += min(0.05, max(0, max_depth - 4) * 0.01)   # parse depth
    if is_multi_part:
        score += 0.05
    score = round(min(1.0, score), 3)

    return QueryAnalysis(
        question_type=question_type,
        complexity_score=score,
        entities=entities,
        sentence_count=sentence_count,
        is_multi_part=is_multi_part,
        features={
            "parse_depth": max_depth,
            "subordinate_clauses": sub_clauses,
            "entity_count": len(entities),
            "sentence_count": sentence_count,
            "backend": "spacy",
        },
    )


def _analyze_fallback(text: str) -> QueryAnalysis:
    """Keyword-only analysis used when spaCy is not available."""
    question_type = _detect_question_type(text)
    # Rough sentence count via punctuation
    sentence_count = max(1, len(re.split(r'[.?!]+', text.strip())) - 1) or 1
    is_multi_part = bool(_RE_MULTI_PART.search(text))

    score = _BASE_COMPLEXITY[question_type]
    score += min(0.12, (sentence_count - 1) * 0.05)
    if is_multi_part:
        score += 0.05
    score = round(min(1.0, score), 3)

    return QueryAnalysis(
        question_type=question_type,
        complexity_score=score,
        entities=[],
        sentence_count=sentence_count,
        is_multi_part=is_multi_part,
        features={"sentence_count": sentence_count, "backend": "keyword"},
    )


class NLPAnalyzer:
    """Analyzes a query to determine complexity and question type for LLM routing."""

    def analyze(self, text: str) -> QueryAnalysis:
        nlp = _get_nlp()
        if nlp is not None:
            try:
                return _analyze_with_spacy(text, nlp)
            except Exception as exc:
                logger.warning("spaCy analysis error, falling back: %s", exc)
        return _analyze_fallback(text)
