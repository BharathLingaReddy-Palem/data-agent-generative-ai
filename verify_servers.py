import urllib.request
import json

# 1. Test Backend Direct
print("--- 1. Testing Backend Direct (http://127.0.0.1:8000/) ---")
try:
    with urllib.request.urlopen("http://127.0.0.1:8000/") as resp:
        data = json.loads(resp.read().decode('utf-8'))
        print("Backend Direct status:", data.get("status"))
        print("Keys active: Groq:", data.get("groq_keys_active"), "NVIDIA:", data.get("nvidia_keys_active"))
except Exception as e:
    print("Backend Direct failed:", e)

# 2. Test Frontend Proxy to Backend (http://localhost:5173/api/sample-datasets)
print("\n--- 2. Testing Frontend Proxy (http://localhost:5173/api/sample-datasets) ---")
try:
    with urllib.request.urlopen("http://localhost:5173/api/sample-datasets") as resp:
        samples = json.loads(resp.read().decode('utf-8'))
        print("Proxy sample-datasets success! Count:", len(samples))
        for s in samples:
            print(" -", s["name"], f"({s['domain']})")
except Exception as e:
    print("Proxy test failed:", e)
