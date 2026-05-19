import requests
host = "http://authentik_server:9000"
headers = {"Authorization": "Bearer swarm-agent-token-secure-123"}

def probe(url):
    try:
        r = requests.get(url, headers=headers)
        print(f"URL: {url} -> {r.status_code} (Len: {len(r.text)})")
        if len(r.text) < 200:
            print(f"Body: {r.text}")
    except Exception as e:
        print(f"URL: {url} -> ERROR: {e}")

probe(host + "/")
probe(host + "/api/v3/")
probe(host + "/api/v3/providers/oauth2/")
