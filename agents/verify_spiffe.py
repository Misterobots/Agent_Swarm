"""
SPIFFE Verification Script

Run this inside the agent-runtime container to verify SPIFFE/SPIRE integration.
"""
import sys
import os
import time
from security.spiffe_auth import get_spiffe_auth

def check_spiffe():
    print("=== SPIFFE Verification ===")
    
    # Check socket existence
    socket_path = os.environ.get("SPIFFE_ENDPOINT_SOCKET", "/var/run/spire/agent.sock")
    print(f"Socket Path: {socket_path}")
    
    if socket_path.startswith("unix://"):
        fs_path = socket_path[7:]
        if os.path.exists(fs_path):
            print(f"[OK] Socket file exists: {fs_path}")
        else:
            print(f"[FAIL] Socket file NOT found: {fs_path}")
            return
            
    # Check py-spiffe import
    try:
        from spiffe import WorkloadApiClient
        print("Successfully imported spiffe.WorkloadApiClient")
    except ImportError as e:
        # WorkloadApiClient = None # This line is not strictly necessary for the script's logic but was in the provided snippet.
        print(f"[FAIL] py-spiffe not installed or import error: {e}")
        import traceback
        traceback.print_exc()
        return

    # Initialize Auth
    print("\nInitializing SpiffeAuth...")
    try:
        auth = get_spiffe_auth()
        if not auth.is_available:
            print("[FAIL] py-spiffe not available or client init failed")
            return
    except Exception as e:
        print(f"[FAIL] Exception initializing auth: {e}")
        return

    # Fetch SVID
    print("\nFetching X.509 SVID...")
    try:
        svid = auth.get_identity()
        if svid:
            print(f"[OK] SVID Fetched!")
            print(f"    SPIFFE ID: {svid.spiffe_id}")
            print(f"    Trust Domain: {svid.spiffe_id.trust_domain}")
        else:
            print("[FAIL] Could not fetch SVID (is agent attested?)")
            return
    except Exception as e:
        print(f"[FAIL] Exception fetching SVID: {e}")
        return

    # Test JWT
    print("\nTesting JWT Generation...")
    try:
        token = auth.get_jwt_token("spiffe://home-ai-lab/agent/router")
        if token:
            print(f"[OK] JWT Generated (len={len(token)})")
        else:
            print("[FAIL] Could not generate JWT")
    except Exception as e:
        print(f"[FAIL] Exception generating JWT: {e}")

if __name__ == "__main__":
    check_spiffe()
