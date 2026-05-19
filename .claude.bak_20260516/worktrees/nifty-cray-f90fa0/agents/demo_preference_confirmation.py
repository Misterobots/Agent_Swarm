"""
HUMAN-IN-THE-LOOP: Preference Confirmation Pattern
===================================================
Demonstrates how an agent can confirm inferred preferences
before executing a task.

Flow:
  User: "Generate an image of a sunset"
  Agent: "I remember you like cyberpunk style. Would you like that, or something else?"
  User: "Yes, cyberpunk please"
  Agent: [Generates cyberpunk sunset]
"""

import os
from typing import Optional
from phi.agent import Agent
from phi.model.ollama import Ollama
from phi.storage.agent.postgres import PgAgentStorage
from phi.tools.function import Function
from config import OLLAMA_HOST, AGNO_DB_URL

# =============================================================================
# 1. PREFERENCE MEMORY STRUCTURE
# =============================================================================

class UserPreferences:
    """
    Stores user preferences in agent memory.
    Retrieved automatically when conversation resumes.
    """
    def __init__(self, storage: PgAgentStorage, user_id: str):
        self.storage = storage
        self.user_id = user_id
        self._preferences = {}
    
    def get(self, key: str, default=None):
        """Get a stored preference."""
        return self._preferences.get(key, default)
    
    def set(self, key: str, value):
        """Set a preference."""
        self._preferences[key] = value
    
    def get_relevant_for_task(self, task_type: str) -> dict:
        """
        Returns preferences relevant to a task type.
        
        Example:
            task_type = "image_generation"
            returns = {"style": "cyberpunk", "color_scheme": "neon"}
        """
        relevant = {}
        
        if task_type == "image_generation":
            if "art_style" in self._preferences:
                relevant["art_style"] = self._preferences["art_style"]
            if "color_scheme" in self._preferences:
                relevant["color_scheme"] = self._preferences["color_scheme"]
        
        elif task_type == "code_generation":
            if "language" in self._preferences:
                relevant["language"] = self._preferences["language"]
            if "framework" in self._preferences:
                relevant["framework"] = self._preferences["framework"]
        
        return relevant


# =============================================================================
# 2. CONFIRMATION HOOK (Human-in-the-Loop)
# =============================================================================

def create_confirmation_agent():
    """
    Creates an agent that confirms preferences before acting.
    Uses Agno's instruction system to enforce confirmation.
    """
    
    agent = Agent(
        name="Preference-Aware Assistant",
        model=Ollama(id="qwen2.5-coder:14b", host=OLLAMA_HOST),
        storage=PgAgentStorage(table_name="preference_agent", db_url=AGNO_DB_URL),
        add_history_to_messages=True,
        num_history_responses=10,
        
        # KEY: Instructions that enforce confirmation behavior
        instructions=[
            "You are a helpful assistant with memory of user preferences.",
            "",
            "=== PREFERENCE CONFIRMATION PROTOCOL ===",
            "When a user makes a creative request (image, 3D, art, etc.):",
            "",
            "1. CHECK MEMORY: Look at the conversation history for stated preferences.",
            "2. IF preferences exist:",
            "   - ALWAYS ask for confirmation before applying them.",
            "   - Format: 'I remember you prefer [X]. Would you like that style, or something different?'",
            "3. IF no preferences exist:",
            "   - Ask what style/approach they'd like.",
            "   - Save their answer as a preference for future use.",
            "4. ONLY execute the task AFTER user confirms.",
            "",
            "Example Dialog:",
            "  User: Generate an image of a sunset",
            "  You: I remember you said you like cyberpunk aesthetics. Would you like a cyberpunk-style sunset, or something different?",
            "  User: Yes, cyberpunk please",
            "  You: [Now generate the image]",
            "",
            "=== PREFERENCE LEARNING ===",
            "When a user expresses a preference, acknowledge and remember it:",
            "  User: I like minimalist designs",
            "  You: Got it! I'll remember you prefer minimalist designs for future suggestions.",
        ],
        
        markdown=True,
        debug_mode=True
    )
    
    return agent


# =============================================================================
# 3. ADVANCED: STATEFUL CONFIRMATION WITH PENDING ACTIONS
# =============================================================================

class ConfirmationState:
    """
    Tracks pending actions that need confirmation.
    Used for more complex multi-step workflows.
    """
    def __init__(self):
        self.pending_action = None
        self.inferred_params = {}
        self.awaiting_confirmation = False
    
    def queue_action(self, action: str, inferred_params: dict):
        """Queue an action for confirmation."""
        self.pending_action = action
        self.inferred_params = inferred_params
        self.awaiting_confirmation = True
    
    def confirm(self) -> dict:
        """User confirmed - return the action to execute."""
        if not self.awaiting_confirmation:
            return None
        
        result = {
            "action": self.pending_action,
            "params": self.inferred_params
        }
        self.clear()
        return result
    
    def modify(self, new_params: dict):
        """User wants to modify the inferred params."""
        self.inferred_params.update(new_params)
    
    def clear(self):
        """Clear pending state."""
        self.pending_action = None
        self.inferred_params = {}
        self.awaiting_confirmation = False


def create_stateful_confirmation_agent():
    """
    Agent with explicit confirmation state management.
    More control than instruction-based approach.
    """
    
    confirmation_state = ConfirmationState()
    
    def request_confirmation(action: str, style: str = None, details: str = None) -> str:
        """
        Tool that queues an action and asks for confirmation.
        
        Args:
            action: The action to perform (e.g., "generate_image")
            style: Inferred style from user preferences
            details: Additional details
        
        Returns:
            Confirmation prompt to show user
        """
        confirmation_state.queue_action(
            action=action,
            inferred_params={"style": style, "details": details}
        )
        
        if style:
            return f"I'll {action} with {style} style. Does that sound good, or would you prefer something different?"
        else:
            return f"I'll {action}. What style would you like?"
    
    def execute_confirmed_action() -> str:
        """
        Tool that executes the confirmed action.
        Only works if user confirmed.
        """
        result = confirmation_state.confirm()
        if not result:
            return "No action pending confirmation."
        
        action = result["action"]
        params = result["params"]
        
        # Execute based on action type
        if action == "generate_image":
            from specialized.image_gen import generate_image
            return generate_image(
                prompt=params.get("details", ""),
                # Could add style modifiers here
            )
        
        return f"Executed {action} with params: {params}"
    
    agent = Agent(
        name="Stateful Confirmation Agent",
        model=Ollama(id="qwen2.5-coder:14b", host=OLLAMA_HOST),
        tools=[
            Function(
                name="request_confirmation",
                description="Queue an action and ask user for confirmation before executing",
                fn=request_confirmation
            ),
            Function(
                name="execute_confirmed_action", 
                description="Execute the action after user confirms",
                fn=execute_confirmed_action
            ),
        ],
        instructions=[
            "When user requests a creative task:",
            "1. Use 'request_confirmation' to ask if inferred preferences are correct",
            "2. Wait for user response",
            "3. If user confirms, use 'execute_confirmed_action'",
            "4. If user modifies, adjust and ask again",
        ],
        markdown=True
    )
    
    return agent


# =============================================================================
# 4. EXAMPLE CONVERSATION FLOW
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("DEMO: Preference Confirmation Pattern")
    print("=" * 70)
    
    agent = create_confirmation_agent()
    
    # Simulate conversation
    print("\n[Turn 1] Establishing preference...")
    response1 = agent.run("I really like cyberpunk and neon aesthetics")
    print(f"User: I really like cyberpunk and neon aesthetics")
    print(f"Agent: {response1.content}")
    
    print("\n[Turn 2] Requesting task (agent should confirm)...")
    response2 = agent.run("Generate an image of a sunset")
    print(f"User: Generate an image of a sunset")
    print(f"Agent: {response2.content}")
    # Expected: "I remember you like cyberpunk. Would you like a cyberpunk sunset?"
    
    print("\n[Turn 3] User confirms...")
    response3 = agent.run("Yes, cyberpunk please")
    print(f"User: Yes, cyberpunk please")
    print(f"Agent: {response3.content}")
    # Expected: Now generates the image
    
    print("\n[Turn 4] User can also override...")
    response4 = agent.run("Actually, make it watercolor style instead")
    print(f"User: Actually, make it watercolor style instead")
    print(f"Agent: {response4.content}")
    # Expected: Uses watercolor instead of cyberpunk
    
    print("\n" + "=" * 70)
    print("KEY TAKEAWAY:")
    print("  The agent ASKS before applying inferred preferences.")
    print("  This prevents unwanted assumptions and keeps user in control.")
    print("=" * 70)
