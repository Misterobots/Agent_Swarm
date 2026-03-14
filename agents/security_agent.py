import logging

# Configuration
# Removed OLLAMA dependencies for speed

import re
import logging

# Configuration
# Removed OLLAMA dependencies for speed

class RunResponse:
    def __init__(self, content):
        self.content = content

class SecurityAgent:
    """
    MAESTRO Layer 6 Security Guard.
    Enforces active defense using Regex patterns and Policy checks.
    """
    def __init__(self):
        self.name = "Security Guard"
        self.policy = self._load_policy()
        self.cmd_blocklist = self.policy.get("command_blocklist", [])
        
    def _load_policy(self):
        import json
        import os
        try:
            # Locate policy file relative to this script
            base_dir = os.path.dirname(__file__)
            policy_path = os.path.join(base_dir, "security_policy.json")
            with open(policy_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Failed to load security policy: {e}")
            return {}

    def run(self, message: str) -> RunResponse:
        """
        Generic security scan of a message or intent.
        """
        # Scan for Command Injection patterns
        for pattern in self.cmd_blocklist:
            if re.search(pattern, message):
                logging.warning(f"SECURITY BLOCK: Attempted dangerous command pattern '{pattern}' in: {message}")
                return RunResponse("UNSAFE: Dangerous Command Pattern Detected")
                
        return RunResponse("SAFE")

    def validate_command(self, command: str) -> bool:
        """
        Specific check for shell commands.
        """
        resp = self.run(command)
        return resp.content == "SAFE"

    def review_dependency(self, package_name: str) -> RunResponse:
        """
        Gatekeeper Logic:
        Checks against BLOCKLIST and PyPI Vulnerabilities.
        """
        # 1. Blocklist Check
        blocklist = self.policy.get("package_blocklist", [])
        if package_name.lower() in blocklist:
            return RunResponse(f"UNSAFE: '{package_name}' is explicitly blocklisted.")
            
        # 2. Vulnerability Check (PyPI)
        vuln_msg = self.check_pypi_issues(package_name)
        if vuln_msg:
             return RunResponse(f"UNSAFE: {vuln_msg}")
            
        return RunResponse("SAFE")

    def check_pypi_issues(self, package_name: str) -> str:
        """Queries PyPI JSON API for vulnerabilities."""
        import requests
        try:
            url = f"https://pypi.org/pypi/{package_name}/json"
            resp = requests.get(url, timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                # Check 'vulnerabilities' key
                vulns = data.get("vulnerabilities", [])
                if vulns:
                     return f"Known Vulnerabilities detected (CVEs: {len(vulns)})"
                
                # Heuristic: Check for 'yanked' release
                # simple check on latest
                latest = data.get("info", {}).get("version")
                if data.get("releases", {}).get(latest, []) and data["releases"][latest][0].get("yanked"):
                    return "Package version yanked from PyPI (Revoked)"
                    
            elif resp.status_code == 404:
                return "Package not found on PyPI (Typo or Private?)"
        except Exception as e:
            logging.warning(f"PyPI Check Failed: {e}")
            return None # Fail open if network down, or fail closed? Let's fail open for now but log.
            
        return None

    def validate_permission(self, agent_name: str, capability: str) -> bool:
        """
        RBAC Enforcement: Checks if the agent has the required capability.
        """
        from registry import registry
        card = registry.get_card(agent_name)
        
        if not card:
            logging.warning(f"SECURITY BLOCK: Unknown Agent '{agent_name}' attempted action.")
            return False
            
        if capability in card.capabilities:
            return True
        
        logging.warning(f"SECURITY BLOCK: Agent '{agent_name}' denied capability '{capability}'.")
        return False

    def evaluate_request(self, req_type: str, details: str) -> RunResponse:
        """
        Governance Assessment:
        Evaluates a user request for potential risks.
        Returns "SAFE" or "UNSAFE: reason".
        """
        if req_type == "PACKAGE":
            # Extract package name (simple check)
            pkg = details.replace("Install package:", "").replace("pip install", "").strip()
            # Handle version specifiers e.g. numpy==1.19
            pkg = pkg.split("=")[0].split("<")[0].split(">")[0].strip()
            return self.review_dependency(pkg)
            
        if req_type == "MODEL":
            # Allow HuggingFace and CivitAI
            allowed = self.policy.get("approved_domains", ["huggingface.co"])
            if any(d in details for d in allowed):
                return RunResponse("SAFE")
            if "http" not in details: # Just a name
                return RunResponse("SAFE")
            return RunResponse("UNSAFE: Internal Policy restricts external model sources.")
            
        if req_type == "OTHER":
            return RunResponse("MANUAL_REVIEW: Non-standard request type.")
            
        return RunResponse("SAFE")

def get_security_agent():
    """
    Returns an instance of the Security Agent.
    """
    return SecurityAgent()

if __name__ == "__main__":
    agent = get_security_agent()
    print(f"Check 'ls -la': {agent.run('ls -la').content}")
    print(f"Check 'rm -rf /': {agent.run('rm -rf /').content}")
    print(f"Check 'django': {agent.review_dependency('django').content}")
