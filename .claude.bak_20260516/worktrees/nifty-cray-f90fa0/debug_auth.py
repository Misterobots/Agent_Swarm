
import requests
import os

URL = "http://localhost:3000/api/chat"
KEY = "sk-sandbox-local"

payload = {
    "messages": [{"role": "user", "content": "ping"}],
    "model": "qwen2.5-coder:14b",
    "temperature": 0
}

def try_header(name, headers):
    print(f"Testing {name}...")
    try:
        res = requests.post(URL, json=payload, headers=headers, timeout=5)
        print(f"Status: {res.status_code}")
        if res.status_code != 401:
            print("SUCCESS!")
            return True
    except Exception as e:
        print(f"Error: {e}")
    return False

# 1. X-API-Key
try_header("X-API-Key", {"X-API-Key": KEY})

# 2. Authorization: Bearer
try_header("Bearer", {"Authorization": f"Bearer {KEY}"})

# 3. Authorization: Raw
try_header("Raw Auth", {"Authorization": KEY})

# 4. Api-Key
try_header("Api-Key", {"Api-Key": KEY})
