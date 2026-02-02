from phi.agent import Agent, RunResponse
from phi.model.ollama import Ollama
import json
import os

class SemanticRouter:
    def __init__(self):
        self.model_name = "llama3:8b-instruct-q4_K_M"
        self.host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        
        self.agent = Agent(
            name="Semantic Router",
            model=Ollama(id=self.model_name, host=self.host),
            description="You are the Frontal Cortex of the AI Swarm.",
            instructions="""
            Your GOAL is to classify the User's Intent into exactly one of these categories:
            
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
            
            OUTPUT FORMAT (JSON ONLY):
            {
                "intent": "CODE" | "IMAGE" | "3D" | "RESEARCH" | "TRAIN" | "AMBIGUOUS",
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
            print(f"[Router Error] {e}")
            return {"intent": "RESEARCH", "confidence": 0.0, "reasoning": "Fallback Error"}

# Global Instance
semantic_router = SemanticRouter()
