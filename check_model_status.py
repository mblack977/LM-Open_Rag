"""
Check current model configuration and test the connection
"""
import requests
import json

BASE_URL = "http://localhost:8080"
OLLAMA_URL = "http://localhost:11434"

def check_current_settings():
    """Check current provider settings"""
    print("="*60)
    print("CHECKING CURRENT SETTINGS")
    print("="*60)
    
    try:
        response = requests.get(f"{BASE_URL}/api/settings")
        if response.status_code == 200:
            settings = response.json()
            print("\n[SUCCESS] Current settings:")
            print(f"  Chat provider: {settings.get('chat_provider', 'Not set')}")
            print(f"  Chat base URL: {settings.get('chat_base_url', 'Not set')}")
            print(f"  Chat model: {settings.get('chat_model', 'Not set')}")
            print(f"  Chat API key: {settings.get('chat_api_key', 'Not set')}")
            print(f"\n  Embedding provider: {settings.get('embedding_provider', 'Not set')}")
            print(f"  Embedding model: {settings.get('embedding_model', 'Not set')}")
            return settings
        else:
            print(f"[ERROR] Status code: {response.status_code}")
            return None
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return None

def check_ollama_models():
    """Check what models are loaded in Ollama"""
    print("\n" + "="*60)
    print("CHECKING OLLAMA MODELS")
    print("="*60)
    
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags")
        if response.status_code == 200:
            data = response.json()
            models = data.get('models', [])
            print(f"\n[SUCCESS] Found {len(models)} models in Ollama:")
            for model in models:
                name = model.get('name', 'Unknown')
                size_mb = model.get('size', 0) / (1024 * 1024)
                print(f"  - {name} ({size_mb:.1f} MB)")
            return models
        else:
            print(f"[ERROR] Status code: {response.status_code}")
            return None
    except Exception as e:
        print(f"[ERROR] Could not connect to Ollama: {str(e)}")
        return None

def test_ollama_chat():
    """Test Ollama chat endpoint"""
    print("\n" + "="*60)
    print("TESTING OLLAMA CHAT")
    print("="*60)
    
    try:
        print("\nSending test message to Ollama...")
        response = requests.post(
            f"{OLLAMA_URL}/v1/chat/completions",
            json={
                "model": "qwen2.5:7b",
                "messages": [
                    {"role": "user", "content": "Say 'Hello, I am working!' in exactly those words."}
                ],
                "max_tokens": 50
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            answer = data.get('choices', [{}])[0].get('message', {}).get('content', '')
            print(f"[SUCCESS] Ollama responded:")
            print(f"  {answer}")
            return True
        else:
            print(f"[ERROR] Status code: {response.status_code}")
            print(f"  Response: {response.text}")
            return False
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return False

def test_rag_system():
    """Test the RAG system with a simple query"""
    print("\n" + "="*60)
    print("TESTING RAG SYSTEM")
    print("="*60)
    
    try:
        print("\nSending test query to RAG system...")
        response = requests.post(
            f"{BASE_URL}/query",
            json={
                "collection": "herb_calibration",
                "query": "What is academic self-concept?",
                "top_k": 5
            },
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            answer = data.get('answer', '')
            word_count = len(answer.split())
            print(f"[SUCCESS] RAG system responded ({word_count} words):")
            print(f"  {answer[:200]}...")
            return True
        else:
            print(f"[ERROR] Status code: {response.status_code}")
            print(f"  Response: {response.text}")
            return False
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return False

def main():
    """Run all checks"""
    print("\n" + "="*60)
    print("MODEL STATUS CHECK")
    print("="*60)
    
    # Check 1: Current settings
    settings = check_current_settings()
    
    # Check 2: Ollama models
    models = check_ollama_models()
    
    # Check 3: Test Ollama chat directly
    ollama_works = test_ollama_chat()
    
    # Check 4: Test RAG system
    rag_works = test_rag_system()
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    if settings:
        chat_provider = settings.get('chat_provider', 'unknown')
        chat_url = settings.get('chat_base_url', 'unknown')
        chat_model = settings.get('chat_model', 'unknown')
        
        print(f"\n[CONFIG] Chat provider: {chat_provider}")
        print(f"[CONFIG] Chat URL: {chat_url}")
        print(f"[CONFIG] Chat model: {chat_model}")
    
    if models:
        print(f"\n[OLLAMA] {len(models)} models available")
        chat_model_found = any('qwen2.5:7b' in m.get('name', '') for m in models)
        if chat_model_found:
            print("[OLLAMA] qwen2.5:7b model is loaded")
        else:
            print("[WARNING] qwen2.5:7b model not found in Ollama")
    
    print(f"\n[TEST] Ollama chat: {'PASS' if ollama_works else 'FAIL'}")
    print(f"[TEST] RAG system: {'PASS' if rag_works else 'FAIL'}")
    
    if ollama_works and rag_works:
        print("\n[SUCCESS] Everything is working! You can now use the chat.")
    else:
        print("\n[WARNING] Some tests failed. Check the errors above.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCheck interrupted by user.")
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
