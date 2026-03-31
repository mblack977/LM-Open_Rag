import math
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class BenchmarkQuery:
    query_id: str
    collection: str
    query_text: str
    query_type: Optional[str] = None
    section_goal: Optional[str] = None
    difficulty: Optional[str] = None
    source: Optional[str] = None
    source_metadata: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    is_active: bool = True
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "query_id": self.query_id,
            "collection": self.collection,
            "query_text": self.query_text,
            "query_type": self.query_type,
            "section_goal": self.section_goal,
            "difficulty": self.difficulty,
            "source": self.source,
            "source_metadata": self.source_metadata,
            "notes": self.notes,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass
class RelevanceLabel:
    query_id: str
    collection: str
    doc_id: Optional[str] = None
    doc_relevance: Optional[str] = None
    chunk_id: Optional[str] = None
    chunk_index: Optional[int] = None
    chunk_relevance: Optional[str] = None
    evidence_role: Optional[str] = None
    annotator: Optional[str] = None
    confidence: float = 1.0
    notes: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "query_id": self.query_id,
            "collection": self.collection,
            "doc_id": self.doc_id,
            "doc_relevance": self.doc_relevance,
            "chunk_id": self.chunk_id,
            "chunk_index": self.chunk_index,
            "chunk_relevance": self.chunk_relevance,
            "evidence_role": self.evidence_role,
            "annotator": self.annotator,
            "confidence": self.confidence,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class RetrievalEvaluator:
    def __init__(self):
        pass
    
    def get_relevant_set(
        self,
        labels: List[RelevanceLabel],
        relevance_threshold: str = "somewhat_relevant",
    ) -> Set[Tuple[str, int]]:
        relevant = set()
        
        relevance_levels = {
            "highly_relevant": 3,
            "somewhat_relevant": 2,
            "not_relevant": 1,
        }
        
        threshold_level = relevance_levels.get(relevance_threshold, 2)
        
        for label in labels:
            if label.doc_relevance:
                level = relevance_levels.get(label.doc_relevance, 1)
                if level >= threshold_level and label.doc_id:
                    relevant.add((label.doc_id, -1))
            
            if label.chunk_relevance:
                chunk_levels = {
                    "supporting_evidence": 3,
                    "background_only": 2,
                    "not_relevant": 1,
                }
                level = chunk_levels.get(label.chunk_relevance, 1)
                if level >= 2 and label.doc_id and label.chunk_index is not None:
                    relevant.add((label.doc_id, label.chunk_index))
        
        return relevant
    
    def precision_at_k(
        self,
        retrieved: List[Tuple[str, int]],
        relevant: Set[Tuple[str, int]],
        k: int,
    ) -> float:
        if k <= 0 or not retrieved:
            return 0.0
        
        top_k = retrieved[:k]
        relevant_retrieved = sum(1 for item in top_k if item in relevant or (item[0], -1) in relevant)
        
        return relevant_retrieved / len(top_k)
    
    def recall_at_k(
        self,
        retrieved: List[Tuple[str, int]],
        relevant: Set[Tuple[str, int]],
        k: int,
    ) -> float:
        if not relevant:
            return 0.0
        
        top_k = retrieved[:k]
        relevant_retrieved = sum(1 for item in top_k if item in relevant or (item[0], -1) in relevant)
        
        return relevant_retrieved / len(relevant)
    
    def average_precision(
        self,
        retrieved: List[Tuple[str, int]],
        relevant: Set[Tuple[str, int]],
    ) -> float:
        if not relevant or not retrieved:
            return 0.0
        
        num_relevant = 0
        sum_precisions = 0.0
        
        for i, item in enumerate(retrieved):
            if item in relevant or (item[0], -1) in relevant:
                num_relevant += 1
                precision_at_i = num_relevant / (i + 1)
                sum_precisions += precision_at_i
        
        return sum_precisions / len(relevant) if len(relevant) > 0 else 0.0
    
    def reciprocal_rank(
        self,
        retrieved: List[Tuple[str, int]],
        relevant: Set[Tuple[str, int]],
    ) -> float:
        for i, item in enumerate(retrieved):
            if item in relevant or (item[0], -1) in relevant:
                return 1.0 / (i + 1)
        return 0.0
    
    def dcg_at_k(
        self,
        retrieved: List[Tuple[str, int]],
        relevance_scores: Dict[Tuple[str, int], float],
        k: int,
    ) -> float:
        dcg = 0.0
        top_k = retrieved[:k]
        
        for i, item in enumerate(top_k):
            rel = relevance_scores.get(item, 0.0)
            if rel == 0.0 and (item[0], -1) in relevance_scores:
                rel = relevance_scores[(item[0], -1)]
            
            dcg += (2 ** rel - 1) / math.log2(i + 2)
        
        return dcg
    
    def ndcg_at_k(
        self,
        retrieved: List[Tuple[str, int]],
        relevance_scores: Dict[Tuple[str, int], float],
        k: int,
    ) -> float:
        dcg = self.dcg_at_k(retrieved, relevance_scores, k)
        
        ideal_retrieved = sorted(
            relevance_scores.keys(),
            key=lambda x: relevance_scores[x],
            reverse=True,
        )
        idcg = self.dcg_at_k(ideal_retrieved, relevance_scores, k)
        
        return dcg / idcg if idcg > 0 else 0.0
    
    def get_relevance_scores(
        self,
        labels: List[RelevanceLabel],
    ) -> Dict[Tuple[str, int], float]:
        scores = {}
        
        relevance_to_score = {
            "highly_relevant": 3.0,
            "somewhat_relevant": 2.0,
            "not_relevant": 0.0,
        }
        
        chunk_relevance_to_score = {
            "supporting_evidence": 3.0,
            "background_only": 1.0,
            "not_relevant": 0.0,
        }
        
        for label in labels:
            if label.doc_relevance and label.doc_id:
                score = relevance_to_score.get(label.doc_relevance, 0.0)
                scores[(label.doc_id, -1)] = max(scores.get((label.doc_id, -1), 0.0), score)
            
            if label.chunk_relevance and label.doc_id and label.chunk_index is not None:
                score = chunk_relevance_to_score.get(label.chunk_relevance, 0.0)
                scores[(label.doc_id, label.chunk_index)] = max(
                    scores.get((label.doc_id, label.chunk_index), 0.0), score
                )
        
        return scores
    
    def evaluate_retrieval(
        self,
        retrieved_results: List[Dict[str, Any]],
        labels: List[RelevanceLabel],
    ) -> Dict[str, float]:
        retrieved = [
            (r.get("doc_id", ""), r.get("chunk_index", -1))
            for r in retrieved_results
            if r.get("doc_id")
        ]
        
        relevant = self.get_relevant_set(labels, relevance_threshold="somewhat_relevant")
        relevance_scores = self.get_relevance_scores(labels)
        
        metrics = {
            "precision_at_5": self.precision_at_k(retrieved, relevant, 5),
            "precision_at_10": self.precision_at_k(retrieved, relevant, 10),
            "recall_at_5": self.recall_at_k(retrieved, relevant, 5),
            "recall_at_10": self.recall_at_k(retrieved, relevant, 10),
            "recall_at_20": self.recall_at_k(retrieved, relevant, 20),
            "ndcg_at_5": self.ndcg_at_k(retrieved, relevance_scores, 5),
            "ndcg_at_10": self.ndcg_at_k(retrieved, relevance_scores, 10),
            "mrr": self.reciprocal_rank(retrieved, relevant),
            "map": self.average_precision(retrieved, relevant),
        }
        
        return metrics
    
    def evaluate_multiple_queries(
        self,
        results_by_query: Dict[str, List[Dict[str, Any]]],
        labels_by_query: Dict[str, List[RelevanceLabel]],
    ) -> Dict[str, Any]:
        all_metrics = []
        metrics_by_type: Dict[str, List[Dict[str, float]]] = {}
        
        for query_id, retrieved_results in results_by_query.items():
            labels = labels_by_query.get(query_id, [])
            if not labels:
                continue
            
            metrics = self.evaluate_retrieval(retrieved_results, labels)
            all_metrics.append(metrics)
            
            query_type = None
            if labels:
                query_type = getattr(labels[0], "query_type", None)
            
            if query_type:
                if query_type not in metrics_by_type:
                    metrics_by_type[query_type] = []
                metrics_by_type[query_type].append(metrics)
        
        if not all_metrics:
            return {
                "num_queries": 0,
                "avg_precision_at_5": 0.0,
                "avg_precision_at_10": 0.0,
                "avg_recall_at_10": 0.0,
                "avg_ndcg_at_10": 0.0,
                "avg_mrr": 0.0,
                "avg_map": 0.0,
            }
        
        avg_metrics = {
            "num_queries": len(all_metrics),
            "avg_precision_at_5": sum(m["precision_at_5"] for m in all_metrics) / len(all_metrics),
            "avg_precision_at_10": sum(m["precision_at_10"] for m in all_metrics) / len(all_metrics),
            "avg_recall_at_5": sum(m["recall_at_5"] for m in all_metrics) / len(all_metrics),
            "avg_recall_at_10": sum(m["recall_at_10"] for m in all_metrics) / len(all_metrics),
            "avg_recall_at_20": sum(m["recall_at_20"] for m in all_metrics) / len(all_metrics),
            "avg_ndcg_at_5": sum(m["ndcg_at_5"] for m in all_metrics) / len(all_metrics),
            "avg_ndcg_at_10": sum(m["ndcg_at_10"] for m in all_metrics) / len(all_metrics),
            "avg_mrr": sum(m["mrr"] for m in all_metrics) / len(all_metrics),
            "avg_map": sum(m["map"] for m in all_metrics) / len(all_metrics),
        }
        
        by_type = {}
        for query_type, type_metrics in metrics_by_type.items():
            by_type[query_type] = {
                "num_queries": len(type_metrics),
                "avg_ndcg_at_10": sum(m["ndcg_at_10"] for m in type_metrics) / len(type_metrics),
                "avg_precision_at_10": sum(m["precision_at_10"] for m in type_metrics) / len(type_metrics),
                "avg_recall_at_10": sum(m["recall_at_10"] for m in type_metrics) / len(type_metrics),
            }
        
        avg_metrics["by_query_type"] = by_type
        
        return avg_metrics
