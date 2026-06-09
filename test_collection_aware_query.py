"""
Test collection-aware chat with a real query
"""
import requests
import json

BASE_URL = "http://localhost:8080"

def test_query():
    """Test the collection-aware chat system"""
    
    query = "What is academic self-concept?"
    
    print("="*70)
    print("TESTING COLLECTION-AWARE CHAT")
    print("="*70)
    print(f"\nQuery: {query}")
    print("\nSending to /v1/chat/completions endpoint...")
    print("(Collection-aware mode should be enabled globally)")
    
    response = requests.post(
        f"{BASE_URL}/v1/chat/completions",
        json={
            "model": "rag-herb_calibration",
            "messages": [
                {"role": "user", "content": query}
            ]
        },
        timeout=120
    )
    
    if response.status_code == 200:
        result = response.json()
        answer = result["choices"][0]["message"]["content"]
        
        print("\n" + "="*70)
        print("RESPONSE")
        print("="*70)
        
        word_count = len(answer.split())
        print(f"\nAnswer length: {word_count} words")
        print(f"\nAnswer:\n{answer}")
        
        # Check for metadata
        if "metadata" in result:
            print("\n" + "="*70)
            print("METADATA (Collection-Aware Mode Active!)")
            print("="*70)
            metadata = result["metadata"]
            print(f"\n  Query intent: {metadata.get('query_intent')}")
            print(f"  Query scope: {metadata.get('query_scope')}")
            print(f"  Documents searched: {metadata.get('documents_searched')}")
            print(f"  Documents used: {metadata.get('documents_used')}")
            print(f"  Chunks used: {metadata.get('chunks_used')}")
            print(f"  Response type: {metadata.get('response_type')}")
            print(f"  Retrieval time: {metadata.get('retrieval_time_ms')}ms")
            print(f"  LLM time: {metadata.get('llm_time_ms')}ms")
            print(f"  Total time: {metadata.get('total_time_ms')}ms")
            
            print("\n[SUCCESS] Collection-aware mode is ACTIVE!")
            print(f"[SUCCESS] Used {metadata.get('documents_used')} documents instead of just 3-5 chunks")
        else:
            print("\n[WARNING] No metadata found - collection-aware mode may not be active")
            print("[INFO] Expected: 400-600 words with metadata")
            print(f"[INFO] Got: {word_count} words without metadata")
        
    else:
        print(f"\n[ERROR] Status code: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    try:
        test_query()
    except requests.exceptions.Timeout:
        print("\n[ERROR] Request timed out - the model may be slow")
        print("Try again or wait for the response")
    except requests.exceptions.ConnectionError:
        print(f"\n[ERROR] Could not connect to {BASE_URL}")
        print("Make sure the server is running")
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
