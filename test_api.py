#!/usr/bin/env python3
import requests
import json

url = "http://localhost:8000/chat"
data = {
    "message": "macbook",
    "session_id": "test125"
}

try:
    response = requests.post(url, json=data, timeout=30)
    print("Status Code:", response.status_code)
    result = response.json()
    print("Response:", result['response'])
    print("State:", result['state'])
    if result.get('products'):
        print("Products found:", len(result['products']))
    else:
        print("No products found")
except Exception as e:
    print("Error:", e)