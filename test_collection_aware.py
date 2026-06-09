"""
Test script for collection-aware chat system.
Demonstrates the difference between traditional and collection-aware retrieval.
"""

import asyncio
import requests
import json
from typing import Dict, Any


BASE_URL = "http://localhost:8000"
COLLECTION = "herb_collection"  # Change to your collection name


def test_traditional_chat(query: str) -> Dict[str, Any]:
    """Test traditional chunk-based RAG."""
    print(f"\n{'='*80}")
    print(f"TRADITIONAL RAG: {query}")
    print('='*80)
    
    response = requests.post(
        f"{BASE_URL}/v1/chat/completions",
        json={
            "model": f"rag-{COLLECTION}",
            "messages": [
                {"role": "user", "content": query}
            ],
            "collection_aware": False  # Explicitly disable
        }
    )
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        return {}
    
    result = response.json()
    answer = result["choices"][0]["message"]["content"]
    
    print(f"\nAnswer ({len(answer)} chars, {len(answer.split())} words):")
    print(answer)
    
    if "metadata" in result:
        print(f"\nMetadata: {json.dumps(result['metadata'], indent=2)}")
    
    return result


def test_collection_aware_chat(query: str) -> Dict[str, Any]:
    """Test collection-aware RAG."""
    print(f"\n{'='*80}")
    print(f"COLLECTION-AWARE RAG: {query}")
    print('='*80)
    
    response = requests.post(
        f"{BASE_URL}/v1/chat/completions",
        json={
            "model": f"rag-{COLLECTION}",
            "messages": [
                {"role": "user", "content": query}
            ],
            "collection_aware": True  # Enable collection-aware mode
        }
    )
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        return {}
    
    result = response.json()
    answer = result["choices"][0]["message"]["content"]
    
    print(f"\nAnswer ({len(answer)} chars, {len(answer.split())} words):")
    print(answer)
    
    if "metadata" in result:
        print(f"\nMetadata:")
        metadata = result["metadata"]
        print(f"  Intent: {metadata.get('query_intent')}")
        print(f"  Scope: {metadata.get('query_scope')}")
        print(f"  Documents searched: {metadata.get('documents_searched')}")
        print(f"  Documents used: {metadata.get('documents_used')}")
        print(f"  Chunks used: {metadata.get('chunks_used')}")
        print(f"  Response type: {metadata.get('response_type')}")
        print(f"  Retrieval time: {metadata.get('retrieval_time_ms')}ms")
        print(f"  LLM time: {metadata.get('llm_time_ms')}ms")
        print(f"  Total time: {metadata.get('total_time_ms')}ms")
    
    return result


def compare_modes(query: str):
    """Compare traditional vs collection-aware for the same query."""
    print(f"\n{'#'*80}")
    print(f"COMPARISON TEST")
    print(f"Query: {query}")
    print('#'*80)
    
    # Test traditional
    trad_result = test_traditional_chat(query)
    trad_answer = trad_result.get("choices", [{}])[0].get("message", {}).get("content", "")
    trad_words = len(trad_answer.split())
    
    # Test collection-aware
    coll_result = test_collection_aware_chat(query)
    coll_answer = coll_result.get("choices", [{}])[0].get("message", {}).get("content", "")
    coll_words = len(coll_answer.split())
    
    # Summary
    print(f"\n{'='*80}")
    print("COMPARISON SUMMARY")
    print('='*80)
    print(f"Traditional answer: {trad_words} words")
    print(f"Collection-aware answer: {coll_words} words")
    print(f"Difference: +{coll_words - trad_words} words ({((coll_words/trad_words - 1) * 100):.1f}% increase)")
    
    if "metadata" in coll_result:
        meta = coll_result["metadata"]
        print(f"\nCollection-aware used:")
        print(f"  - {meta.get('documents_used')} documents (from {meta.get('documents_searched')} total)")
        print(f"  - {meta.get('chunks_used')} chunks")
        print(f"  - Intent: {meta.get('query_intent')}")
        print(f"  - Response type: {meta.get('response_type')}")


def test_different_intents():
    """Test different query intents."""
    test_queries = [
        # Concept explanation
        ("What is academic self-concept?", "concept_explanation"),
        
        # Research synthesis
        ("What are the main findings about academic self-concept and achievement?", "research_synthesis"),
        
        # Comparison
        ("What is the difference between academic self-concept and self-efficacy?", "comparison"),
        
        # Evidence lookup
        ("What evidence supports the big-fish-little-pond effect?", "evidence_lookup"),
        
        # Factual lookup
        ("Who are the main authors in this collection?", "factual_lookup"),
    ]
    
    print(f"\n{'#'*80}")
    print("TESTING DIFFERENT QUERY INTENTS")
    print('#'*80)
    
    for query, expected_intent in test_queries:
        result = test_collection_aware_chat(query)
        
        if "metadata" in result:
            actual_intent = result["metadata"].get("query_intent")
            match = "✓" if actual_intent == expected_intent else "✗"
            print(f"\n{match} Expected: {expected_intent}, Got: {actual_intent}")


def test_dedicated_endpoint(query: str):
    """Test the dedicated collection-aware endpoint."""
    print(f"\n{'='*80}")
    print(f"DEDICATED ENDPOINT TEST: {query}")
    print('='*80)
    
    response = requests.post(
        f"{BASE_URL}/v1/chat/completions/collection-aware",
        json={
            "model": f"rag-{COLLECTION}",
            "messages": [
                {"role": "user", "content": query}
            ]
        }
    )
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        return
    
    result = response.json()
    answer = result["choices"][0]["message"]["content"]
    
    print(f"\nAnswer ({len(answer.split())} words):")
    print(answer[:500] + "..." if len(answer) > 500 else answer)
    
    if "metadata" in result:
        print(f"\nMetadata: {json.dumps(result['metadata'], indent=2)}")


def main():
    """Run all tests."""
    print("="*80)
    print("COLLECTION-AWARE CHAT SYSTEM TEST SUITE")
    print("="*80)
    print(f"Base URL: {BASE_URL}")
    print(f"Collection: {COLLECTION}")
    print("="*80)
    
    # Test 1: Compare modes for a concept question
    compare_modes("What is academic self-concept?")
    
    # Test 2: Test different intents
    test_different_intents()
    
    # Test 3: Test dedicated endpoint
    test_dedicated_endpoint("Explain the relationship between academic self-concept and achievement across these studies.")
    
    print(f"\n{'='*80}")
    print("ALL TESTS COMPLETED")
    print('='*80)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user.")
    except requests.exceptions.ConnectionError:
        print(f"\n\nError: Could not connect to {BASE_URL}")
        print("Make sure the server is running with: python main.py")
    except Exception as e:
        print(f"\n\nError: {str(e)}")
        import traceback
        traceback.print_exc()
