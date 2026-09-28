#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.request
import urllib.error

# Default Host (Internal Docker Network)
# Can be overridden by env var SWARM_HOST
DEFAULT_HOST = os.getenv("SWARM_HOST", "http://agent-runtime:8000")

def submit_request(r_type, description):
    url = f"{DEFAULT_HOST}/api/v1/request"
    
    # MAESTRO L7: Identity
    api_key = os.getenv("SWARM_API_KEY")
    if not api_key:
        print("[ERROR] SWARM_API_KEY not found in environment. Cannot authenticate.")
        sys.exit(1)

    payload = {
        "type": r_type.upper(),
        "description": description
        # "user": ... Removed. Identity is derived from Key.
    }
    
    try:
        data = json.dumps(payload).encode('utf-8')
        headers = {
            'Content-Type': 'application/json',
            'X-Swarm-Source': api_key
        }
        req = urllib.request.Request(url, data=data, headers=headers)
        
        print(f"Talking to Swarm at {DEFAULT_HOST}...")
        with urllib.request.urlopen(req, timeout=5) as response:
            resp_data = response.read()
            data = json.loads(resp_data)
            print(f"\n[SUCCESS] Request Submitted!")
            print(f"ID: {data['id']}")
            print(f"Status: {data['status']}")
            print(f"Please wait for Admin approval.")
            
    except urllib.error.HTTPError as e:
        print(f"\n[ERROR] HTTP Error {e.code}: {e.reason}")
        print(e.read().decode())
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"\n[ERROR] Connection Failed: {e.reason}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Failed to submit request: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Swarm Governance Request CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Package Command
    pkg_parser = subparsers.add_parser("package", help="Request a Python/System package")
    pkg_parser.add_argument("name", help="Name of the package (e.g. numpy)")
    
    # Model Command
    model_parser = subparsers.add_parser("model", help="Request a new AI Model")
    model_parser.add_argument("name", help="Name/URL of the model")

    # Generic Request
    req_parser = subparsers.add_parser("ask", help="Generic request")
    req_parser.add_argument("description", help="Description of what you need")

    args = parser.parse_args()

    if args.command == "package":
        submit_request("PACKAGE", f"Install package: {args.name}")
    elif args.command == "model":
        submit_request("MODEL", f"Download model: {args.name}")
    elif args.command == "ask":
        submit_request("OTHER", args.description)

if __name__ == "__main__":
    main()
