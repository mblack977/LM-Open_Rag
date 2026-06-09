"""
Enable collection-aware chat mode globally
"""
import os
from pathlib import Path

def enable_collection_aware():
    """Add USE_COLLECTION_AWARE_CHAT=true to .env file"""
    
    env_path = Path("c:/Herb Project/LM-Open-Rag/.env")
    
    print("Enabling collection-aware chat mode...")
    
    # Read existing .env content
    if env_path.exists():
        with open(env_path, 'r') as f:
            lines = f.readlines()
    else:
        lines = []
    
    # Check if already set
    found = False
    for i, line in enumerate(lines):
        if line.startswith('USE_COLLECTION_AWARE_CHAT'):
            lines[i] = 'USE_COLLECTION_AWARE_CHAT=true\n'
            found = True
            print("[INFO] Updated existing USE_COLLECTION_AWARE_CHAT setting")
            break
    
    # Add if not found
    if not found:
        lines.append('\n# Enable collection-aware chat for comprehensive research synthesis\n')
        lines.append('USE_COLLECTION_AWARE_CHAT=true\n')
        print("[INFO] Added USE_COLLECTION_AWARE_CHAT=true to .env")
    
    # Write back
    with open(env_path, 'w') as f:
        f.writelines(lines)
    
    print("\n[SUCCESS] Collection-aware chat is now enabled!")
    print("\nYou need to restart the server for this to take effect:")
    print("  1. Stop the current server (Ctrl+C)")
    print("  2. Run: python main.py")
    print("\nAfter restart, your queries will use:")
    print("  - Multi-stage retrieval (metadata -> documents -> chunks)")
    print("  - Collection-level synthesis across 5-20 documents")
    print("  - Intent-specific response templates")
    print("  - 400-600 word comprehensive answers")

if __name__ == "__main__":
    try:
        enable_collection_aware()
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
