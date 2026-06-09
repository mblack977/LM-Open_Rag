import logging
from typing import Any, Dict, List, Optional

from .collection_retriever import EvidencePack, DocumentMetadata, ChunkResult
from .lm_studio_client import LMStudioClient

logger = logging.getLogger(__name__)


class ResponseGenerator:
    """
    Generates structured responses based on query intent and evidence pack.
    Uses different templates for different query types.
    """
    
    def __init__(self, llm_client: LMStudioClient):
        self._llm_client = llm_client
    
    async def generate_response(self, evidence_pack: EvidencePack) -> Dict[str, Any]:
        """
        Generate a response based on the evidence pack and query plan.
        """
        plan = evidence_pack.plan
        
        if plan.response_format == "definition_plus_collection_synthesis":
            return await self._generate_concept_explanation(evidence_pack)
        elif plan.response_format == "synthesis_with_evidence":
            return await self._generate_research_synthesis(evidence_pack)
        elif plan.response_format == "comparative_synthesis":
            return await self._generate_comparison(evidence_pack)
        elif plan.response_format == "evidence_summary":
            return await self._generate_evidence_summary(evidence_pack)
        elif plan.response_format == "direct_answer":
            return await self._generate_direct_answer(evidence_pack)
        else:
            return await self._generate_comprehensive_answer(evidence_pack)
    
    async def _generate_concept_explanation(self, evidence_pack: EvidencePack) -> Dict[str, Any]:
        """Generate a concept explanation response."""
        context = self._build_context(evidence_pack)
        doc_summary = self._build_document_summary(evidence_pack.candidate_documents)

        system_prompt = (
            "You are a knowledgeable research assistant. Answer questions clearly and helpfully, "
            "drawing from the research evidence provided. Match your response length to the complexity "
            "of the question — a simple definition gets a concise answer, a nuanced question gets more depth. "
            "Write in plain prose. Do not use markdown headers, numbered sections, or bullet points unless "
            "the question explicitly asks for a list. Never pad the answer."
        )

        user_prompt = f"""Answer the following question using the research evidence below.

QUESTION: {evidence_pack.query_text}

RELEVANT ARTICLES ({len(evidence_pack.candidate_documents)} identified):
{doc_summary}

RESEARCH EVIDENCE:
{context}

Draw from the evidence to give a clear, accurate answer. Where multiple sources address the concept, synthesize them rather than listing each one separately. Be as brief or as detailed as the question warrants.

Answer:"""

        answer = await self._llm_client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            max_tokens=500
        )
        
        return {
            "answer": answer,
            "sources": self._build_sources(evidence_pack),
            "documents_used": len(evidence_pack.candidate_documents),
            "chunks_used": len(evidence_pack.chunks),
            "response_type": "concept_explanation"
        }
    
    async def _generate_research_synthesis(self, evidence_pack: EvidencePack) -> Dict[str, Any]:
        """Generate a research synthesis response."""
        context = self._build_context(evidence_pack)
        doc_summary = self._build_document_summary(evidence_pack.candidate_documents)

        system_prompt = (
            "You are a knowledgeable research assistant. Answer questions clearly and helpfully, "
            "drawing from the research evidence provided. Match your response length to the complexity "
            "of the question. Write in plain prose — no markdown headers, no numbered sections, no bullet points. "
            "Synthesize across sources rather than summarising each one in turn. Never pad the answer."
        )

        user_prompt = f"""Answer the following question using the research evidence below.

QUESTION: {evidence_pack.query_text}

RELEVANT ARTICLES ({len(evidence_pack.candidate_documents)} identified):
{doc_summary}

RESEARCH EVIDENCE:
{context}

Identify the key findings, patterns, and themes across the studies. Include specific evidence where it strengthens the answer. Be as brief or detailed as the question warrants.

Answer:"""

        answer = await self._llm_client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            max_tokens=500
        )
        
        return {
            "answer": answer,
            "sources": self._build_sources(evidence_pack),
            "documents_used": len(evidence_pack.candidate_documents),
            "chunks_used": len(evidence_pack.chunks),
            "response_type": "research_synthesis"
        }
    
    async def _generate_comparison(self, evidence_pack: EvidencePack) -> Dict[str, Any]:
        """Generate a comparative analysis response."""
        context = self._build_context(evidence_pack)
        doc_summary = self._build_document_summary(evidence_pack.candidate_documents)
        
        system_prompt = (
            "You are a knowledgeable research assistant. Answer questions clearly and helpfully, "
            "drawing from the research evidence provided. Write in plain prose — no markdown headers, "
            "no numbered sections, no bullet points unless the question asks for a list. Never pad the answer."
        )
        
        user_prompt = f"""Answer the following comparison question using the research evidence below.

QUESTION: {evidence_pack.query_text}

RELEVANT ARTICLES ({len(evidence_pack.candidate_documents)} identified):
{doc_summary}

RESEARCH EVIDENCE:
{context}

Compare clearly and accurately. Highlight similarities and differences where they matter. Be as brief or detailed as the question warrants — don't pad.

Answer:"""

        answer = await self._llm_client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            max_tokens=500
        )
        
        return {
            "answer": answer,
            "sources": self._build_sources(evidence_pack),
            "documents_used": len(evidence_pack.candidate_documents),
            "chunks_used": len(evidence_pack.chunks),
            "response_type": "comparison"
        }
    
    async def _generate_evidence_summary(self, evidence_pack: EvidencePack) -> Dict[str, Any]:
        """Generate an evidence-focused summary."""
        context = self._build_context(evidence_pack)
        doc_summary = self._build_document_summary(evidence_pack.candidate_documents)
        
        system_prompt = (
            "You are a knowledgeable research assistant. Answer questions clearly and helpfully, "
            "drawing from the research evidence provided. Write in plain prose — no markdown headers, "
            "no numbered sections, no bullet points unless the question asks for a list. Never pad the answer."
        )
        
        user_prompt = f"""Answer the following question using the research evidence below.

QUESTION: {evidence_pack.query_text}

RELEVANT ARTICLES ({len(evidence_pack.candidate_documents)} identified):
{doc_summary}

RESEARCH EVIDENCE:
{context}

Summarise what the evidence shows. Include key findings and note any important limitations or caveats. Be as brief or detailed as the question warrants.

Answer:"""

        answer = await self._llm_client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        return {
            "answer": answer,
            "sources": self._build_sources(evidence_pack),
            "documents_used": len(evidence_pack.candidate_documents),
            "chunks_used": len(evidence_pack.chunks),
            "response_type": "evidence_summary"
        }
    
    async def _generate_direct_answer(self, evidence_pack: EvidencePack) -> Dict[str, Any]:
        """Generate a direct, concise answer for factual queries."""
        doc_summary = self._build_document_summary(evidence_pack.candidate_documents)
        
        system_prompt = "You are a helpful research assistant. Provide direct, concise answers to factual questions."
        
        user_prompt = f"""Answer this factual question directly and concisely.

QUESTION: {evidence_pack.query_text}

DOCUMENT INFORMATION:
{doc_summary}

Provide a brief, direct answer (1-3 sentences).

Your answer:"""

        answer = await self._llm_client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=500
        )
        
        return {
            "answer": answer,
            "sources": self._build_sources(evidence_pack),
            "documents_used": len(evidence_pack.candidate_documents),
            "chunks_used": 0,
            "response_type": "direct_answer"
        }
    
    async def _generate_comprehensive_answer(self, evidence_pack: EvidencePack) -> Dict[str, Any]:
        """Generate a comprehensive answer for general questions."""
        context = self._build_context(evidence_pack)
        doc_summary = self._build_document_summary(evidence_pack.candidate_documents)
        
        system_prompt = (
            "You are an expert research assistant. Provide comprehensive, well-structured "
            "answers that synthesize information from multiple research sources."
        )
        
        user_prompt = f"""Answer the following question using the research evidence below.

QUESTION: {evidence_pack.query_text}

RELEVANT ARTICLES ({len(evidence_pack.candidate_documents)} identified):
{doc_summary}

RESEARCH EVIDENCE:
{context}

Give a clear, accurate answer. Draw from the evidence and synthesize across sources where relevant. Match the length to the complexity of the question.

Answer:"""

        answer = await self._llm_client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            max_tokens=500
        )
        
        return {
            "answer": answer,
            "sources": self._build_sources(evidence_pack),
            "documents_used": len(evidence_pack.candidate_documents),
            "chunks_used": len(evidence_pack.chunks),
            "response_type": "comprehensive_answer"
        }
    
    def _build_context(self, evidence_pack: EvidencePack) -> str:
        """Build the context string from chunks and abstracts."""
        context_parts: List[str] = []

        # Add abstracts (capped to keep context manageable)
        if evidence_pack.plan.use_abstracts:
            for doc in evidence_pack.candidate_documents[:5]:
                if doc.abstract:
                    context_parts.append(
                        f"[{doc.title or doc.filename or 'Unknown'}]\n"
                        f"Authors: {doc.authors or 'Unknown'}\n"
                        f"Abstract: {doc.abstract[:400]}"
                    )

        # Add top chunks — limit text per chunk to keep total context under ~4000 tokens
        for chunk in evidence_pack.chunks[:12]:
            chunk_header = f"[{chunk.title or chunk.filename or 'Unknown'}]"
            if chunk.section:
                chunk_header += f" ({chunk.section})"
            context_parts.append(f"{chunk_header}\n{chunk.text[:500]}")

        return "\n\n---\n\n".join(context_parts)
    
    def _build_document_summary(self, documents: List[DocumentMetadata]) -> str:
        """Build a summary of relevant documents."""
        if not documents:
            return "No documents found."
        
        summary_parts: List[str] = []
        for i, doc in enumerate(documents[:15], 1):
            title = doc.title or doc.filename or "Unknown"
            authors = doc.authors or "Unknown authors"
            summary_parts.append(f"{i}. {title} ({authors})")
        
        return "\n".join(summary_parts)
    
    def _build_sources(self, evidence_pack: EvidencePack) -> List[Dict[str, Any]]:
        """Build source citations for the response."""
        sources: List[Dict[str, Any]] = []
        seen_docs: set = set()
        
        # Add documents
        for doc in evidence_pack.candidate_documents[:10]:
            if doc.doc_id not in seen_docs:
                sources.append({
                    "doc_id": doc.doc_id,
                    "title": doc.title,
                    "authors": doc.authors,
                    "filename": doc.filename,
                    "relevance_score": doc.relevance_score
                })
                seen_docs.add(doc.doc_id)
        
        # Add chunk sources
        for chunk in evidence_pack.chunks[:15]:
            if chunk.doc_id not in seen_docs:
                sources.append({
                    "doc_id": chunk.doc_id,
                    "title": chunk.title,
                    "authors": chunk.authors,
                    "filename": chunk.filename,
                    "chunk_index": chunk.chunk_index,
                    "score": chunk.score
                })
                seen_docs.add(chunk.doc_id)
        
        return sources
