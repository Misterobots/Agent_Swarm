import logging

# Configuration
# Removed OLLAMA dependencies for speed

class RunResponse:
    def __init__(self, content):
        self.content = content

class MockSecurityAgent:
    """
    A lightweight mock agent that mimics the Phi Agent interface
    but runs pure Python logic to avoid LLM latency.
    """
    def __init__(self):
        self.name = "Security Guard (Mock)"
        
    def run(self, message: str) -> RunResponse:
        # Instant response
        # In a real scenario, this could use Regex or lightweight classifiers
        return RunResponse("SAFE")

    def review_dependency(self, package_name: str) -> RunResponse:
        """
        Gatekeeper Logic:
        In a real system, this would check PyPI malware databases,
        license compatibility, and version security.
        """
        # Mock Logic: Block suspicious names
        suspicious = ["os", "sys", "subprocess", "shutil"]
        if package_name in suspicious:
            return RunResponse("UNSAFE")
            
        return RunResponse("SAFE")

def get_security_agent():
    """
    Returns an instance of the Security Agent.
    """
    return MockSecurityAgent()

if __name__ == "__main__":
    agent = get_security_agent()
    print(agent.run("Validate: 'rm -rf /'").content)
