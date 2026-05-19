import sys
sys.path.insert(0, "/app/agents")
from provider_keys import get_key
import psycopg2
from config import TEMPLATE_DB_URL
import urllib.request, urllib.error, json

conn = psycopg2.connect(TEMPLATE_DB_URL); cur = conn.cursor()
cur.execute("SELECT user_id FROM swarm.provider_api_keys WHERE provider=%s LIMIT 1", ("nvidia",))
row = cur.fetchone()
if not row:
    print("no NVIDIA key stored"); sys.exit()
uid = row[0]; print("uid:", uid[:16])
rec = get_key(uid, "nvidia"); key = rec.get_api_key()
print("key prefix:", key[:8])

models = [
    "nvidia/llama-3.1-nemotron-70b-instruct",
    "nvidia/llama-3.3-nemotron-super-49b-v1",
    "nvidia/llama-3.1-nemotron-nano-8b-v1",
    "nvidia/llama-3.1-nemotron-ultra-253b-v1",
    "mistralai/mistral-nemotron",
    "deepseek-ai/deepseek-v4-pro",
]
for model in models:
    payload = {"model": model, "messages":[{"role":"user","content":"hi"}], "max_tokens": 5, "stream": False}
    req = urllib.request.Request("https://integrate.api.nvidia.com/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type":"application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)
        print("OK  ", model, "->", repr(d["choices"][0]["message"]["content"][:40]))
    except urllib.error.HTTPError as e:
        print("FAIL", model, "->", e.code, e.reason, "|", e.read().decode("utf-8","replace")[:200])
    except Exception as e:
        print("ERR ", model, "->", type(e).__name__, e)
