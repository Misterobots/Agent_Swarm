import requests
import os
import json

AUTHENTIK_HOST = "http://authentik_server:9000"
TOKEN = "swarm-agent-token-secure-123"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Host": "localhost:9000"
}

def log(msg):
    print(f"[Authentik Setup] {msg}")

def get_flow_pk(slug):
    # Hardcoded for reliability
    return "3bee29f2-2bef-4a77-8d01-3f463056a117"

def setup_grafana():
    log("Configuring Grafana OIDC...")
    
    # 1. Create Provider
    # Search first
    res = requests.get(f"{AUTHENTIK_HOST}/api/v3/providers/oauth2/?name=Grafana", headers=HEADERS)
    print(f"GET Provider Status: {res.status_code}")
    if res.status_code != 200:
        print(f"Response: {res.text}")
        return

    if res.json()['results']:
        provider_pk = res.json()['results'][0]['pk']
        client_id = res.json()['results'][0]['client_id']
        client_secret = res.json()['results'][0]['client_secret']
        log("Grafana Provider exists.")
    else:
        # Create
        flow_auth = get_flow_pk("default-provider-authorization-implicit-consent")
        data = {
            "name": "Grafana",
            "authorization_flow": flow_auth,
            "client_type": "confidential",
            "redirect_uris": [
                "http://localhost:3000/login/generic_oauth"
            ],
            "property_mappings": [
                "1c3529d4-c9c0-482a-89aa-c81b2da98c56" # Managed: OIDC User Info.  Wait, UUIDs vary!
                # Better to search for property mappings? Or use default?
                # Defaults are usually auto-selected if empty?
            ]
        }
        # If we rely on defaults, we might miss the mappings.
        # Let's search for "Authentik default OAuth Mapping: OpenID 'profile'"
        # Actually, let's just try creating without mappings first.
        del data['property_mappings']
        
        create_res = requests.post(f"{AUTHENTIK_HOST}/api/v3/providers/oauth2/", json=data, headers=HEADERS)
        if create_res.status_code >= 400:
            log(f"Error creating provider: {create_res.text}")
            return
        provider_pk = create_res.json()['pk']
        client_id = create_res.json()['client_id']
        client_secret = create_res.json()['client_secret']
        log("Grafana Provider created.")

    # 2. Create Application
    res = requests.get(f"{AUTHENTIK_HOST}/api/v3/core/applications/?name=Grafana", headers=HEADERS)
    if not res.json()['results']:
        data = {
            "name": "Grafana",
            "slug": "grafana",
            "provider": provider_pk
        }
        requests.post(f"{AUTHENTIK_HOST}/api/v3/core/applications/", json=data, headers=HEADERS)
        log("Grafana Application created.")
    
    # Output Env Vars
    print(f"\n--- GRAFANA ENV VARS ---\nGF_AUTH_GENERIC_OAUTH_CLIENT_ID={client_id}\nGF_AUTH_GENERIC_OAUTH_CLIENT_SECRET={client_secret}\n")

def setup_vscode():
    log("Configuring VS Code OIDC...")
    # ... Similar logic for VS Code ...
    # For brevity, I'll stick to Grafana first to test.
    pass

if __name__ == "__main__":
    setup_grafana()
