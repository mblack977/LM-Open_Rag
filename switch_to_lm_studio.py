"""
Quick script to switch chat provider to LM Studio
"""
import requests
import json

BASE_URL = "http://localhost:8080"

def switch_to_lm_studio():
    """Switch the chat provider to LM Studio"""
    
    print("Switching chat provider to LM Studio...")
    
    response = requests.post(
        f"{BASE_URL}/settings/provider",
        json={
            "chat_provider": "lm_studio",
            "chat_base_url": "http://localhost:1234/v1",
            "chat_api_key": "lm-studio"
        }
    )
    
    if response.status_code == 200:
        print("✅ Successfully switched to LM Studio")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    try:
        switch_to_lm_studio()
    except requests.exceptions.ConnectionError:
        print(f"❌ Error: Could not connect to {BASE_URL}")
        print("Make sure the server is running")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
