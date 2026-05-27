from phi.agent import Agent, RunResponse
from phi.model.ollama import Ollama
import json
import os
import re
import logging
from config import get_ollama_options

_router_logger = logging.getLogger("SemanticRouter")

# ---------------------------------------------------------------------------
# Keyword Fast-Path: Reserved for genuinely unambiguous, single-intent signals
# whose vocabulary cannot appear in a different-intent context.
# Everything else goes to the LLM router so confidence scores are real.
# Each tuple: (compiled regex, intent, base confidence).
# ---------------------------------------------------------------------------
_FAST_PATH_RULES: list[tuple[re.Pattern, str, float]] = [
    # VISION — user is asking to look at an image they already have
    (re.compile(
        r"what do you see|describe this image|analyze this image|what is in this picture"
        r"|read this screenshot|ocr|identify.*image|what'?s happening in this photo"
        r"|look at this|what'?s in this (image|photo|screenshot)",
        re.I,
    ), "VISION", 0.92),

    # ACTION_FIGURE — highly domain-specific vocabulary, no overlap with other intents
    (re.compile(
        r"action figure|posable|ball joint|figurine|poseable|articulated figure|3d print figure",
        re.I,
    ), "ACTION_FIGURE", 0.95),

    # IOT_CONTROL — smart home commands; verb + device phrasing is unambiguous
    (re.compile(
        r"\b(turn (on|off)|lights?\s+(on|off)|set (temperature|thermostat)|unlock\b"
        r"|home assistant|(run|activate|trigger)\s+scene\b)",
        re.I,
    ), "IOT_CONTROL", 0.92),

    # IOT_DEV — firmware / embedded; vocabulary never appears in general prompts
    (re.compile(
        r"\b(wokwi|flash esp32|compile firmware|mqtt|arduino|simulate circuit)\b",
        re.I,
    ), "IOT_DEV", 0.90),

    # TRAIN — explicit system-teaching directives
    (re.compile(
        r"\b(remember that|learn this|correction:|from now on|teach you)\b",
        re.I,
    ), "TRAIN", 0.92),
]


class SemanticRouter:
    def __init__(self):
        # Use select_available_model so routing survives VRAM pressure.
        # ROUTER_MODEL defaults to qwen3:8b (fits alongside Klein).
        # Falls back to qwen3:8b explicitly if env isn't set.
        from utils.gpu_queue import select_available_model
        _preferred = os.getenv("ROUTER_MODEL", os.getenv("PRIMARY_MODEL", "qwen3:8b"))
        self.model_name, self.host = select_available_model(_preferred, ["qwen3:8b"])

        # Self-Healing: Ensure model exists before Agent init
        self.ensure_model(self.model_name)

        self.agent = Agent(
            name="Semantic Router",
            model=Ollama(id=self.model_name, host=self.host, client_kwargs={"timeout": 300.0}, options=get_ollama_options(self.model_name)),
            description="You are the Frontal Cortex of the AI Swarm.",
            instructions="""
            You are the Frontal Cortex of the AI Swarm. Your GOAL is to function as a strict Intent Classifier.
            Analyze the User's input and select exactly ONE category.

            **CONTEXTUAL ANALYSIS RULES**:
            If the input contains "Original Request", "System Question", and "User Answer", merge the "User Answer" into the "Original Request" context to deduce the final intent.

            CATEGORIES:
            1. **CONVERSATION**: Greetings, casual chat, small talk, simple factual questions, meta-questions about the AI system itself, simple list requests, or anything social in nature. Default for any message that is unclear but does not require specialized tools. ALWAYS use this for requests to "list", "show", "what tools", "what files", "what access" especially if user adds "succinct", "brief", "quick", or "short". (Keywords: "hello", "hi", "how are you", "what is", "tell me about", "who are you", "what can you do", "what do you have access to", "what files do you have", "what tools", "what are your capabilities", "tell me about yourself", "how do you work", "help me understand you", "list the", "show me", "succinct", "brief", "quick list")
            2. **CODE**: Software engineering, writing scripts (Python/JS/etc.), debugging, fixing errors, building apps, or improving existing code. The user must be asking you to BUILD, WRITE, FIX, DEBUG, MODIFY, IMPROVE, OPTIMIZE, or WORK ON software — not merely asking about files or capabilities. (Keywords: "write script", "fix bug", "function", "develop", "code", "implement", "refactor", "improve the code", "work on the code", "optimize", "enhance", "update the implementation")
            3. **DEVOPS**: Infrastructure, Docker, Kubernetes, CI/CD pipelines, Linux administration, networking, shell scripts, server configuration, or cloud deployment. (Keywords: "docker", "kubernetes", "deploy", "nginx", "server", "firewall", "pipeline", "bash script", "systemd", "compose")
            4. **DATA**: Data analysis, SQL queries, CSV/JSON processing, statistics, charts, dashboards, or data transformation. (Keywords: "query", "sql", "analyze data", "csv", "dataframe", "statistics", "chart", "pandas", "aggregate")
            5. **IMAGE**: Generating 2D visual art, photos, concept art, or textures. (Keywords: "draw", "generate image", "picture of", "photo", "paint", "illustration")
            6. **3D**: Creating 3D geometry, meshes, or 3D models. (Keywords: "3d model", "mesh", "glb", "obj", "forge", "blender")
            7. **ACTION_FIGURE**: Converting an image into a 3D-printable posable action figure with joints. (Keywords: "action figure", "posable", "ball joint", "articulated", "figurine", "3d print figure", "poseable", "joint")
            8. **RESEARCH**: Deep knowledge quests, academic research, History, Literature, Humanities, Philosophy, Science facts, or multi-source analysis. Requires depth beyond a quick answer. (Keywords: "research", "analyze", "compare", "history of", "literature review", "what caused", "deep dive")
            8b. **CREATIVE**: Creative or fictional writing — scene descriptions, stories, narratives, poems, roleplay scenarios, fictional world/character descriptions, lore, fan fiction, or any request to write/describe imaginative or fictional content. The user wants generated written content, not information. (Keywords: "write a scene", "describe a scene", "vivid description", "write a story", "creative writing", "fiction", "roleplay", "shadowrun", "lore", "narrative", "set in the universe of", "detailed description of")
            9. **DOCUMENTATION**: Rewriting text, formatting markdown documents, technical writing, or summarizing large RAG files. (Keywords: "rewrite", "document", "summarize", "format", "write a guide", "write a readme")
            10. **TRAIN**: Teaching the system new rules, instructions, or corrections to its behavior. (Keywords: "remember that", "learn this", "correction:", "from now on")
            11. **IOT_CONTROL**: Turning on/off smart home devices, lights, sending raw commands to home automation. (Keywords: "turn on", "lights", "temperature", "unlock", "scene", "home assistant")
            12. **IOT_DEV**: Developing firmware, simulating circuits, or raw MQTT backend development. (Keywords: "simulate", "wokwi", "flash esp32", "compile firmware", "mqtt", "arduino")
            13. **VISION**: Analyzing, describing, or answering questions about an existing image or screenshot. The user is asking the AI to LOOK AT an image they provide, NOT to generate a new one. (Keywords: "what do you see", "describe this image", "analyze this image", "what is in this picture", "read this screenshot", "OCR", "identify", "what's happening in this photo", "look at this")
            14. **COORDINATE**: The user is requesting a complex, multi-step task that requires decomposition into subtasks, parallel research, synthesis of findings, and coordinated implementation. This is NOT for simple one-shot requests — only for tasks that genuinely need multiple workers collaborating. DO NOT USE for simple information requests like "list X" or "what tools" even if they mention planning/building. (Keywords: "plan and build", "coordinate", "multi-step", "build a full", "design and implement", "create a complete", "end-to-end", "full stack", "set up a system"). ANTI-PATTERNS: "list tools", "show me", "what do you have", "succinct list" → these are CONVERSATION, not COORDINATE.

            OUTPUT FORMAT CHECKLIST (JSON ONLY):
            {
                "intent": "<EXACT STRING FROM CATEGORIES OR 'AMBIGUOUS'>",
                "confidence": <float between 0.0 and 1.0>,
                "reasoning": "<short logical deduction of why this category fits>",
                "disambiguation_question": "<if AMBIGUOUS, a question to ask the user to clarify>"
            }

            CRITICAL DIRECTIVES:
            - CONVERSATION is the default for social, general, or ambiguous inputs. Prefer CONVERSATION over AMBIGUOUS unless the user is asking for a specific capability you cannot determine.
            - META-QUESTIONS: If the user asks about YOUR files, YOUR access, YOUR tools, YOUR capabilities, or YOUR identity — ALWAYS classify as CONVERSATION. These are questions ABOUT the system, not requests to BUILD software. Example: "What files do you have access to?" → CONVERSATION (not CODE).
            - Only classify as CODE when the user explicitly wants you to BUILD, WRITE, FIX, DEBUG, MODIFY, IMPROVE, OPTIMIZE, or WORK ON software artifacts. "Let's work on improving the X code/feature" = CODE. "help me improve the implementation" = CODE.
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

    def fast_classify(self, user_input: str) -> dict | None:
        """
        Keyword fast-path: returns a routing decision in <1ms if a regex
        pattern matches, or None to fall through to the LLM router.
        """
        text = user_input
        # If this is a composite ambiguity-resolution prompt, extract the original request
        if "Original Request:" in text and "User Answer:" in text:
            # Use the combined text for matching
            pass

        for pattern, intent, confidence in _FAST_PATH_RULES:
            if pattern.search(text):
                _router_logger.info(
                    f"[Router] Fast-path match: {intent} ({confidence*100:.0f}%) "
                    f"for '{text[:80]}'"
                )
                return {
                    "intent": intent,
                    "confidence": confidence,
                    "reasoning": f"Keyword fast-path: matched {intent} pattern",
                }
        return None

    def route(self, user_input: str) -> dict:
        """
        Analyzes input and returns routing decision, with a multi-step confidence cascade.
        Fast-path keywords are checked first (<1ms); LLM is only called for ambiguous inputs.
        """
        # --- Fast-path: regex keyword matching (saves 300-1200ms) ---
        fast_result = self.fast_classify(user_input)
        if fast_result:
            return fast_result

        _router_logger.info(f"[Router] No fast-path match — falling back to LLM router")
        max_retries = 2

        for attempt in range(max_retries):
            try:
                # Provide a sharper prompt on retry
                if attempt == 0:
                    prompt = f"Input: {user_input}"
                else:
                    prompt = f"Input: {user_input}\n\nWARNING: Your previous classification was AMBIGUOUS or had low confidence (< 0.6). Please re-evaluate carefully using strict logical deduction. Ensure you provide a distinct categorization. If truly ambiguous, you MUST provide a disambiguation_question."

                response: RunResponse = self.agent.run(prompt)

                # Parse JSON — response.content can be a dict when phidata auto-parses
                # JSON responses (even without json_mode=True on older builds), so handle both.
                content = response.content
                if isinstance(content, dict):
                    decision = content
                else:
                    if "```json" in content:
                        content = content.replace("```json", "").replace("```", "")
                    decision = json.loads(content.strip())
                confidence = float(decision.get("confidence", 0.0))

                # Success criteria: High confidence and not explicitly ambiguous
                if confidence >= 0.75 and decision.get("intent") != "AMBIGUOUS":
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

