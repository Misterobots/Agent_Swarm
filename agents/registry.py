from pydantic import BaseModel, Field
from typing import List, Optional
import uuid

class AgentCard(BaseModel):
    """
    Immutable Identity Card for AI Agents.
    Adheres to MAESTRO Layer 7 & A2A Protocol.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    role: str
    description: str
    security_level: str # L1_PUBLIC, L2_USER, L3_ADMIN, L4_SYSTEM
    capabilities: List[str] = []
    endpoint: str

class AgentRegistry:
    """
    Central Authority for Agent Identity.
    """
    def __init__(self):
        self._registry = {}
        self._initialize_system_agents()

    def _initialize_system_agents(self):
        """Register the core Swarm agents."""
        
        # 1. The Code Developer (formerly Architect)
        self.register(AgentCard(
            name="Code Developer",
            role="Full Stack & System Engineer",
            description="Autonomous coding, refactoring, and system architecture specialist.",
            security_level="L3_ADMIN",
            capabilities=["file_ops.write", "file_ops.read", "terminal.exec", "git.ops", "git.status", "git.branch", "git.commit", "git.diff"],
            endpoint="local://agents.architect_agent"
        ))

        # 2. The Art Director (Creative)
        self.register(AgentCard(
            name="Art Director",
            role="Creative Lead",
            description="Visual synthesis and prompt engineering specialist.",
            security_level="L2_USER",
            capabilities=["image_gen.generate", "file_ops.read"], # No write access to code
            endpoint="local://agents.specialized.image_gen"
        ))

        # 3. The Router (Neural Cortex)
        self.register(AgentCard(
            name="Router",
            role="Neural Dispatcher",
            description="Llama-3 powered intent classification system.",
            security_level="L4_SYSTEM",
            capabilities=["route.intent", "ambiguity.check"],
            endpoint="local://agents.semantic_router"
        ))

        # 4. Security Agent (The Guard)
        self.register(AgentCard(
            name="Security",
            role="Compliance Officer",
            description="Enforces MAESTRO protocols and file guards.",
            security_level="L4_SYSTEM",
            capabilities=["audit.scan", "process.kill"],
            endpoint="local://agents.security_agent"
        ))

        # 5. IoT Controller (Hardware Specialist)
        self.register(AgentCard(
            name="IoT Controller",
            role="IoT Developer & Automation Engineer",
            description="Expertise in IoT Development, Automation, and Hardware Integration (MQTT, NFC, ESPHome, GPIO, Arduino).",
            security_level="L2_OPERATOR",
            capabilities=["iot.list", "iot.control", "mqtt.pub", "hardware.flash", "iot.simulate"],
            endpoint="local://agents.specialized.iot_agent"
        ))

        # 6. Voice Cloning Expert
        self.register(AgentCard(
            name="Voice Cloning Expert",
            role="Voice Synthesis Specialist",
            description="Expert in voice cloning and speech generation using Qwen3-TTS.",
            security_level="L2_USER",
            capabilities=["voice.clone", "voice.speak"],
            endpoint="local://agents.specialized.voice_cloning"
        ))

        # 7. Librarian (Research Agent)
        self.register(AgentCard(
            name="Librarian",
            role="Research & Knowledge Specialist",
            description="Workspace search, documentation lookup, and general knowledge Q&A.",
            security_level="L1_PUBLIC",
            capabilities=["workspace.search", "workspace.read", "file_ops.read"],
            endpoint="local://agents.router.librarian"
        ))

    def register(self, card: AgentCard):
        self._registry[card.name] = card

    def get_card(self, name: str) -> Optional[AgentCard]:
        return self._registry.get(name)

    def list_agents(self) -> List[AgentCard]:
        return list(self._registry.values())

# Global Singleton
registry = AgentRegistry()
