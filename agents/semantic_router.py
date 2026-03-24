from phi.agent import Agent, RunResponse
from phi.model.ollama import Ollama
import json
import os

class SemanticRouter:
    def __init__(self):
        # Nemotron-Orchestrator-8B: Nvidia's purpose-built multi-agent routing model
        # Runs on Dell R730 (RTX 3070 Ti 8GB) via SECONDARY_OLLAMA_HOST
        self.model_name = os.getenv("ROUTER_MODEL", "nemotron-orchestrator:8b")
        from utils.gpu_queue import get_best_host_for_model
        self.host = get_best_host_for_model(self.model_name)
        
        # Self-Healing: Ensure model exists before Agent init
        self.ensure_model(self.model_name)
        
        self.agent = Agent(
            name="Semantic Router",
            model=Ollama(id=self.model_name, host=self.host, client_kwargs={"timeout": 300.0}),
            description="You are the Frontal Cortex of the AI Swarm.",
            instructions="""
            You are the Frontal Cortex of the AI Swarm. Your GOAL is to function as a strict Intent Classifier.
            Analyze the User's input and select exactly ONE category.
            
            **CONTEXTUAL ANALYSIS RULES**:
            If the input contains "Original Request", "System Question", and "User Answer", merge the "User Answer" into the "Original Request" context to deduce the final intent.
            
            CATEGORIES:
            1. **CONVERSATION**: Greetings, casual chat, small talk, simple factual questions, or anything social in nature. Default for any message that is unclear but does not require specialized tools. (Keywords: "hello", "hi", "how are you", "what is", "tell me about", "who are you", "what can you do")
            2. **CODE**: Software engineering, writing scripts (Python/JS/etc.), debugging, fixing errors, or building apps. (Keywords: "write script", "fix bug", "function", "develop", "code", "implement", "refactor")
            3. **DEVOPS**: Infrastructure, Docker, Kubernetes, CI/CD pipelines, Linux administration, networking, shell scripts, server configuration, or cloud deployment. (Keywords: "docker", "kubernetes", "deploy", "nginx", "server", "firewall", "pipeline", "bash script", "systemd", "compose")
            4. **DATA**: Data analysis, SQL queries, CSV/JSON processing, statistics, charts, dashboards, or data transformation. (Keywords: "query", "sql", "analyze data", "csv", "dataframe", "statistics", "chart", "pandas", "aggregate")
            5. **IMAGE**: Generating 2D visual art, photos, concept art, or textures. (Keywords: "draw", "generate image", "picture of", "photo", "paint", "illustration")
            6. **3D**: Creating 3D geometry, meshes, or 3D models. (Keywords: "3d model", "mesh", "glb", "obj", "forge", "blender")
            7. **RESEARCH**: Deep knowledge quests, academic research, History, Literature, Humanities, Philosophy, Science facts, or multi-source analysis. Requires depth beyond a quick answer. (Keywords: "research", "analyze", "compare", "history of", "literature review", "what caused", "deep dive")
            8. **DOCUMENTATION**: Rewriting text, formatting markdown documents, technical writing, or summarizing large RAG files. (Keywords: "rewrite", "document", "summarize", "format", "write a guide", "write a readme")
            9. **TRAIN**: Teaching the system new rules, instructions, or corrections to its behavior. (Keywords: "remember that", "learn this", "correction:", "from now on")
            10. **IOT_CONTROL**: Turning on/off smart home devices, lights, sending raw commands to home automation. (Keywords: "turn on", "lights", "temperature", "unlock", "scene", "home assistant")
            11. **IOT_DEV**: Developing firmware, simulating circuits, or raw MQTT backend development. (Keywords: "simulate", "wokwi", "flash esp32", "compile firmware", "mqtt", "arduino")

            OUTPUT FORMAT CHECKLIST (JSON ONLY):
            {
                "intent": "<EXACT STRING FROM CATEGORIES OR 'AMBIGUOUS'>",
                "confidence": <float between 0.0 and 1.0>,
                "reasoning": "<short logical deduction of why this category fits>",
                "disambiguation_question": "<if AMBIGUOUS, a question to ask the user to clarify>"
            }

            CRITICAL DIRECTIVES:
            - CONVERSATION is the default for social, general, or ambiguous inputs. Prefer CONVERSATION over AMBIGUOUS unless the user is asking for a specific capability you cannot determine.
            - Only output AMBIGUOUS if the user is asking for something that could be CODE, IMAGE, DEVOPS, or another capability-specific intent but you cannot tell which.
            - If confidence is < 0.50, output AMBIGUOUS with a disambiguation_question.
            - Output VALID JSON only. Do not wrap in markdown or add conversational text.
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
            # 1. Check availability with a short timeout
            tags_res = requests.get(f"{self.host}/api/tags", timeout=5)
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
        Analyzes input and returns routing decision, with a multi-step confidence cascade.
        """
        max_retries = 2
        
        for attempt in range(max_retries):
            try:
                # Provide a sharper prompt on retry
                if attempt == 0:
                    prompt = f"Input: {user_input}"
                else:
                    prompt = f"Input: {user_input}\n\nWARNING: Your previous classification was AMBIGUOUS or had low confidence (< 0.6). Please re-evaluate carefully using strict logical deduction. Ensure you provide a distinct categorization. If truly ambiguous, you MUST provide a disambiguation_question."

                response: RunResponse = self.agent.run(prompt)
                
                # Parse JSON
                content = response.content
                if "```json" in content:
                    content = content.replace("```json", "").replace("```", "")
                
                decision = json.loads(content.strip())
                confidence = float(decision.get("confidence", 0.0))
                
                # Success criteria: High confidence and not explicitly ambiguous
                if confidence >= 0.6 and decision.get("intent") != "AMBIGUOUS":
                    return decision
                    
            except Exception as e:
                error_str = str(e)
                print(f"[Router Error - Attempt {attempt+1}] {error_str}")
                
                if "404" in error_str and "not found" in error_str:
                    return {
                        "intent": "RESEARCH",
                        "confidence": 0.0, 
                        "reasoning": f"CRITICAL: Model '{self.model_name}' missing. Please run 'ollama pull {self.model_name}'"
                    }

        # Fallback to the last parsed decision if retries run out
        if 'decision' in locals() and isinstance(decision, dict):
            return decision

        return {"intent": "CONVERSATION", "confidence": 0.0, "reasoning": "Fallback Error (Router failed all retries)"}

# Global Singleton (Lazy Loaded)
_router_instance = None

def get_semantic_router() -> SemanticRouter:
    global _router_instance
    if _router_instance is None:
        _router_instance = SemanticRouter()
    return _router_instance
