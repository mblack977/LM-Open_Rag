"""
Configure the system to use Ollama with the correct settings
"""
import requests
import json

BASE_URL = "http://localhost:8080"

def configure_ollama():
    """Configure chat provider to use Ollama"""
    
    print("Configuring system to use Ollama...")
    print("Chat model: qwen2.5:7b")
    print("Embedding model: mxbai-embed-large")
    
    # Update provider settings
    response = requests.post(
        f"{BASE_URL}/api/settings",
        json={
            "chat_provider": "lm_studio",  # Use lm_studio client (OpenAI-compatible)
            "chat_base_url": "http://localhost:11434/v1",  # Ollama's OpenAI-compatible endpoint
            "chat_api_key": "ollama",
            "chat_model": "qwen2.5:7b"
        }
    )
    
    if response.status_code == 200:
        print("[SUCCESS] Successfully configured Ollama")
        result = response.json()
        print(f"\nCurrent settings:")
        print(f"  Chat provider: {result.get('chat_provider')}")
        print(f"  Chat base URL: {result.get('chat_base_url')}")
        print(f"  Chat model: {result.get('chat_model')}")
        print(f"\nYou can now use the chat!")
    else:
        print(f"[ERROR] Status code: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    try:
        configure_ollama()
    except requests.exceptions.ConnectionError:
        print(f"[ERROR] Could not connect to {BASE_URL}")
        print("Make sure the server is running")
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
