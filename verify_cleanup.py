"""Verify herb_calibration cleanup"""
import httpx
import json

# Check Qdrant
r = httpx.get('http://localhost:6333/collections/herb_calibration')
result = r.json()['result']
print('Qdrant herb_calibration:')
print(f'  Points: {result["points_count"]}')
print(f'  Vector size: {result["config"]["params"]["vectors"]["text"]["size"]}')
print(f'  Status: {result["status"]}')
