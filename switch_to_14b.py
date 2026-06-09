"""
Switch to the larger qwen2.5:14b model
"""
import requests
import json

BASE_URL = "http://localhost:8080"

def switch_to_14b():
    """Switch chat model to qwen2.5:14b"""
    
    print("Switching to qwen2.5:14b model...")
    print("This is the larger, more capable model (8.6 GB)")
    
    # Update provider settings
    response = requests.post(
        f"{BASE_URL}/api/settings",
        json={
            "chat_provider": "lm_studio",
            "chat_base_url": "http://localhost:11434/v1",
            "chat_api_key": "ollama",
            "chat_model": "qwen2.5:14b"  # Changed to 14b
        }
    )
    
    if response.status_code == 200:
        print("[SUCCESS] Successfully switched to qwen2.5:14b")
        print("\nVerifying settings...")
        
        # Verify the change
        verify_response = requests.get(f"{BASE_URL}/api/settings")
        if verify_response.status_code == 200:
            settings = verify_response.json()
            print(f"\nCurrent settings:")
            print(f"  Chat model: {settings.get('chat_model')}")
            print(f"  Chat provider: {settings.get('chat_provider')}")
            print(f"  Chat base URL: {settings.get('chat_base_url')}")
            print(f"\nThe 14b model is now active!")
            print(f"You should get higher quality, more detailed answers.")
        
    else:
        print(f"[ERROR] Status code: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    try:
        switch_to_14b()
    except requests.exceptions.ConnectionError:
        print(f"[ERROR] Could not connect to {BASE_URL}")
        print("Make sure the server is running")
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
