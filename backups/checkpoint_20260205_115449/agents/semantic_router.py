from phi.agent import Agent, RunResponse
from phi.model.ollama import Ollama
import json
import os

class SemanticRouter:
    def __init__(self):
        # Use standard Llama3.2 (fast & efficient for routing)
        self.model_name = "llama3.2" 
        self.host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        
        # Self-Healing: Ensure model exists before Agent init
        self.ensure_model(self.model_name)
        
        self.agent = Agent(
            name="Semantic Router",
            model=Ollama(id=self.model_name, host=self.host),
            description="You are the Frontal Cortex of the AI Swarm.",
            instructions="""
            Your GOAL is to classify the User's Intent into exactly one of these categories.
            
            **CONTEXTUAL ANALYSIS**:
            If the input contains "Original Request", "System Question", and "User Answer":
            - Use the "User Answer" to clarify the "Original Request".
            - Example: Original="make it pop", Answer="add 3d depth" -> Intent: 3D.
            
            CATEGORIES:
            1. **CODE**: Writing python/js scripts, debugging, fixing errors, building apps.
               - Keywords: "write script", "fix bug", "function", "develop".
            2. **IMAGE**: Generating visual art, photos, 3D textures, concept art.
               - Keywords: "draw", "generate image", "picture of".
            3. **3D**: Creating 3D models, geometry, meshes (e.g., "make a 3d model").
               - Keywords: "3d model", "mesh", "glb", "obj".
            4. **RESEARCH**: general questions, facts, logic, jokes, explanations.
               - Keywords: "explain", "who is", "tell me", "research".
            5. **TRAIN**: Teaching the system new rules or corrections.
               - Keywords: "remember that", "learn this".
            6. **IOT_CONTROL**: Controlling smart home devices, lights, switches.
               - Keywords: "turn on", "lights", "temperature", "unlock", "scene".
            7. **IOT_DEV**: Developing firmware, simulating circuits, or raw MQTT.
               - Keywords: "simulate", "wokwi", "flash esp32", "compile firmware", "mqtt publish".
            
            OUTPUT FORMAT (JSON ONLY):
            {
                "intent": "CODE" | "IMAGE" | "3D" | "RESEARCH" | "TRAIN" | "IOT_CONTROL" | "IOT_DEV" | "AMBIGUOUS",
                "confidence": <float 0.0-1.0>,
                "reasoning": "<short explanation>",
                "disambiguation_question": "<if AMBIGUOUS, ask unique question>"
            }
            
            RULES:
            - If confidence is below 0.6, return "AMBIGUOUS".
            - Output VALID JSON only. No markdown.
            """,
            show_tool_calls=False,
            json_mode=True
        )

    def ensure_model(self, model_name: str):
        """
        Checks if model exists in Ollama. If not, pulls it.
        """
        import requests
        try:
            # 1. Check availability
            tags_res = requests.get(f"{self.host}/api/tags")
            if tags_res.status_code == 200:
                models = [m['name'] for m in tags_res.json().get('models', [])]
                # Check for exact match or formatted match
                if any(model_name in m for m in models):
                    return # Model exists
            
            # 2. Pull if missing
            print(f"--- [Router] Model '{model_name}' missing. Auto-pulling... ---")
            pull_res = requests.post(f"{self.host}/api/pull", json={"name": model_name, "stream": False})
            
            if pull_res.status_code == 200:
                print(f"--- [Router] Successfully pulled '{model_name}'. ---")
            else:
                print(f"--- [Router] Failed to pull '{model_name}': {pull_res.text} ---")
                
        except Exception as e:
            print(f"--- [Router] Self-Healing Failed: {e} ---")

    def route(self, user_input: str) -> dict:
        """
        Analyzes input and returns routing decision.
        """
        try:
            response: RunResponse = self.agent.run(f"Input: {user_input}")
            # Parse JSON
            content = response.content
            # Cleanup potential markdown wrapping
            if "```json" in content:
                content = content.replace("```json", "").replace("```", "")
            
            decision = json.loads(content.strip())
            return decision
        except Exception as e:
            # Fallback if LLM fails
            error_str = str(e)
            print(f"[Router Error] {error_str}")
            
            if "404" in error_str and "not found" in error_str:
                return {
                    "intent": "RESEARCH", # Default to Chat
                    "confidence": 0.0, 
                    "reasoning": f"CRITICAL: Model '{self.model_name}' missing. Please run 'ollama pull {self.model_name}'"
                }
            
            return {"intent": "RESEARCH", "confidence": 0.0, "reasoning": "Fallback Error (Router)"}

# Global Instance
semantic_router = SemanticRouter()
