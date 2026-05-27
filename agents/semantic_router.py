from phi.agent import Agent, RunResponse
from phi.model.ollama import Ollama
import hashlib
import json
import math
import os
import re
import time
import logging
from config import get_ollama_options

_router_logger = logging.getLogger("SemanticRouter")

# ---------------------------------------------------------------------------
# Keyword Fast-Path
# Reserved for genuinely unambiguous, single-intent signals whose vocabulary
# cannot appear in a different-intent context.  Intentionally kept narrow —
# false positives here bypass the full classifier.
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

    # IMAGE — generate visual art (not looking at existing images)
    (re.compile(
        r"\b(generate|create|make|draw|paint|render|design)\b.{0,40}"
        r"\b(image|photo|picture|artwork|illustration|concept art|wallpaper|portrait|scene)\b"
        r"|\btext.?to.?image\b|stable diffusion",
        re.I,
    ), "IMAGE", 0.90),

    # CREATIVE — fiction / story / narrative writing
    (re.compile(
        r"\b(write|tell|craft|compose|narrate|describe)\b.{0,40}"
        r"\b(story|scene|narrative|fiction|roleplay|fanfic|lore|poem|sonnet|dialogue)\b"
        r"|\b(short story|flash fiction|creative writing|in the style of|in the universe of)\b",
        re.I,
    ), "CREATIVE", 0.88),

    # RESEARCH — deep knowledge / analysis; phrases that imply multi-source depth
    (re.compile(
        r"\b(research|deep dive|literature review|comprehensive (overview|analysis|summary)"
        r"|history of|origins? of|evolution of|compare and contrast"
        r"|what caused|why did|how did .+ (happen|develop|evolve))\b",
        re.I,
    ), "RESEARCH", 0.87),

    # COORDINATE — multi-part build/design/implement with explicit scope
    (re.compile(
        r"\b(build|create|develop|implement|set up|design)\b.{0,60}"
        r"\b(full|complete|end.to.end|entire|whole|from scratch)\b"
        r"|\b(full.stack|end.to.end system|multi.step|step.by.step plan)\b"
        r"|\b(plan and (build|implement|develop|create))\b",
        re.I,
    ), "COORDINATE", 0.87),

    # DEVOPS — infra-specific keywords unlikely to appear in general chat
    (re.compile(
        r"\b(docker(file)?|kubernetes|kubectl|helm|terraform|ansible"
        r"|nginx|traefik|haproxy|systemd|cron job|ci/?cd|github actions"
        r"|deploy to (aws|gcp|azure|vps|production)|firewall rules?)\b",
        re.I,
    ), "DEVOPS", 0.90),

    # CONVERSATION — clear greetings and meta-questions about the system
    (re.compile(
        r"^(hi|hello|hey|good (morning|afternoon|evening)|howdy|what'?s up)[,!.?\s]*$"
        r"|^(who are you|what (are|can) you do|tell me about yourself"
        r"|how do you work|what tools do you have|what.+capabilities)\??$",
        re.I,
    ), "CONVERSATION", 0.90),
]

# ---------------------------------------------------------------------------
# Exemplar bank — used by the embedding classifier (Fix 4).
# 3-5 representative sentences per intent.  Keep them DISTINCT from each other
# so cosine similarity correctly discriminates close intents.
# ---------------------------------------------------------------------------
_EXEMPLARS: dict[str, list[str]] = {
    "CONVERSATION": [
        "Hello, how are you?",
        "What can you help me with?",
        "Tell me about yourself",
        "What tools do you have access to?",
        "How does the swarm work?",
    ],
    "CODE": [
        "Fix the bug in my authentication middleware",
        "Refactor this function to be more efficient",
        "Write a Python script to parse JSON files",
        "Help me debug this TypeScript error",
        "Improve the performance of this database query",
    ],
    "DEVOPS": [
        "Deploy this Docker container to production",
        "Set up a GitHub Actions CI/CD pipeline",
        "Configure nginx as a reverse proxy",
        "Write a bash script to automate backups",
        "Troubleshoot this Kubernetes pod crash",
    ],
    "IMAGE": [
        "Generate a photorealistic portrait of a cat",
        "Create concept art for a cyberpunk city",
        "Draw an illustration of a mountain landscape",
        "Make an image of a futuristic spaceship",
        "Paint a watercolor scene of a forest",
    ],
    "RESEARCH": [
        "Research the history of the Byzantine Empire",
        "Give me a deep dive into quantum computing",
        "Compare the causes of World War I and II",
        "What is the current state of fusion energy research?",
        "Analyze the philosophical implications of consciousness",
    ],
    "CREATIVE": [
        "Write a short story about a time traveler",
        "Describe a vivid scene in a cyberpunk dystopia",
        "Write dialogue between two rival space captains",
        "Create lore for my fantasy world",
        "Write a poem about autumn",
    ],
    "COORDINATE": [
        "Build a complete web app with authentication and a dashboard",
        "Design and implement a full microservices architecture",
        "Create a multi-step data pipeline from scratch",
        "Plan and build an end-to-end recommendation system",
        "Set up a complete home automation system with sensors and alerts",
    ],
    "DOCUMENTATION": [
        "Write a README for this project",
        "Summarize this technical document",
        "Rewrite this API documentation in clearer language",
        "Format this markdown guide",
        "Create technical specs for this feature",
    ],
    "DATA": [
        "Write a SQL query to aggregate monthly sales",
        "Analyze this CSV and show me the trends",
        "Build a pandas dataframe transformation pipeline",
        "Create a chart showing user growth over time",
        "Help me understand these statistics",
    ],
    "VISION": [
        "What do you see in this image?",
        "Describe what's happening in this screenshot",
        "Read the text from this photo",
        "Identify the objects in this picture",
        "Analyze this diagram and explain it",
    ],
}

# ---------------------------------------------------------------------------
# Result cache — TTL-keyed by normalized input hash (Fix 2).
# Prevents re-classifying identical or near-identical messages on every turn.
# ---------------------------------------------------------------------------
_ROUTE_CACHE: dict[str, tuple[dict, float]] = {}
_ROUTE_CACHE_TTL = 120.0   # seconds
_ROUTE_CACHE_MAX = 512


def _cache_key(text: str) -> str:
    normalized = " ".join(text.lower().split())[:512]
    return hashlib.md5(normalized.encode()).hexdigest()


def _cache_get(text: str) -> dict | None:
    key = _cache_key(text)
    entry = _ROUTE_CACHE.get(key)
    if entry is None:
        return None
    result, ts = entry
    if time.time() - ts > _ROUTE_CACHE_TTL:
        _ROUTE_CACHE.pop(key, None)
        return None
    return dict(result)  # return a defensive copy


def _cache_put(text: str, result: dict) -> None:
    global _ROUTE_CACHE
    key = _cache_key(text)
    _ROUTE_CACHE[key] = (result, time.time())
    if len(_ROUTE_CACHE) > _ROUTE_CACHE_MAX:
        cutoff = time.time() - _ROUTE_CACHE_TTL
        _ROUTE_CACHE = {k: v for k, v in _ROUTE_CACHE.items() if v[1] > cutoff}


# ---------------------------------------------------------------------------
# Embedding-based classifier (Fix 4).
# Uses nomic-embed-text via Ollama (~10 ms on Turing).  Cosine-similarity
# against per-intent exemplars replaces the LLM call for clear-cut cases,
# saving 1–5 s per request.  Falls through to the LLM router when similarity
# is below the confidence threshold.
# ---------------------------------------------------------------------------
_EMBED_CONFIDENCE_THRESHOLD = 0.82   # minimum cosine sim to trust embedding result
_EMBED_MODEL = "nomic-embed-text"
_EMBED_HOST: str | None = None       # resolved lazily

# Cached exemplar embeddings — populated on first use
_exemplar_embeddings: dict[str, list[list[float]]] | None = None
_exemplar_lock = __import__("threading").Lock()


def _get_embed_host() -> str:
    global _EMBED_HOST
    if _EMBED_HOST is None:
        # nomic-embed-text fits on Turing (8 GB); prefer secondary host
        _EMBED_HOST = os.getenv(
            "EMBED_HOST",
            os.getenv("SECONDARY_OLLAMA_HOST", os.getenv("OLLAMA_HOST", "http://localhost:11434")),
        )
    return _EMBED_HOST


def _embed(texts: list[str]) -> list[list[float]] | None:
    """Call Ollama /api/embed and return embedding vectors, or None on error."""
    import requests as _req
    host = _get_embed_host()
    try:
        resp = _req.post(
            f"{host}/api/embed",
            json={"model": _EMBED_MODEL, "input": texts},
            timeout=8,
        )
        if resp.status_code == 200:
            data = resp.json()
            # Ollama returns {"embeddings": [[...],...]} for /api/embed
            return data.get("embeddings") or data.get("embedding")
    except Exception as e:
        _router_logger.debug(f"[Router] Embedding call failed: {e}")
    return None


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _build_exemplar_embeddings() -> dict[str, list[list[float]]] | None:
    """Embed all exemplar sentences once and cache the vectors."""
    all_texts: list[str] = []
    intent_map: list[str] = []
    for intent, examples in _EXEMPLARS.items():
        for ex in examples:
            all_texts.append(ex)
            intent_map.append(intent)

    vectors = _embed(all_texts)
    if vectors is None or len(vectors) != len(all_texts):
        return None

    result: dict[str, list[list[float]]] = {}
    for intent, vec in zip(intent_map, vectors):
        result.setdefault(intent, []).append(vec)
    return result


def _embedding_classify(user_input: str) -> dict | None:
    """
    Attempt to classify via embedding similarity.
    Returns a routing dict (same shape as LLM router output) or None if
    below threshold / embedding service unavailable.
    """
    global _exemplar_embeddings

    # Build exemplar cache once (thread-safe)
    with _exemplar_lock:
        if _exemplar_embeddings is None:
            _exemplar_embeddings = _build_exemplar_embeddings()
            if _exemplar_embeddings is None:
                _router_logger.debug("[Router] Embedding exemplar build failed — skipping embed tier")
                return None

    # Embed the input
    input_vecs = _embed([user_input])
    if not input_vecs:
        return None
    input_vec = input_vecs[0]

    # Find the intent whose exemplars have the highest average similarity
    best_intent: str | None = None
    best_sim = 0.0
    second_sim = 0.0

    for intent, ex_vecs in _exemplar_embeddings.items():
        sims = [_cosine(input_vec, ev) for ev in ex_vecs]
        avg_sim = sum(sims) / len(sims)
        if avg_sim > best_sim:
            second_sim = best_sim
            best_sim = avg_sim
            best_intent = intent
        elif avg_sim > second_sim:
            second_sim = avg_sim

    if best_intent is None or best_sim < _EMBED_CONFIDENCE_THRESHOLD:
        _router_logger.debug(
            f"[Router] Embed: best={best_intent} sim={best_sim:.3f} < threshold {_EMBED_CONFIDENCE_THRESHOLD} — falling through"
        )
        return None

    # Extra guard: if the top two intents are very close, defer to LLM
    margin = best_sim - second_sim
    if margin < 0.04:
        _router_logger.debug(
            f"[Router] Embed: margin {margin:.3f} too narrow ({best_intent} vs runner-up) — falling through"
        )
        return None

    _router_logger.info(
        f"[Router] Embed fast-path: {best_intent} sim={best_sim:.3f} margin={margin:.3f}"
    )
    return {
        "intent": best_intent,
        "confidence": round(min(best_sim, 0.97), 4),
        "reasoning": f"Embedding similarity fast-path (sim={best_sim:.3f}, margin={margin:.3f})",
    }


# ---------------------------------------------------------------------------
# SemanticRouter
# ---------------------------------------------------------------------------

class SemanticRouter:
    def __init__(self):
        from utils.gpu_queue import select_available_model
        _preferred = os.getenv("ROUTER_MODEL", os.getenv("PRIMARY_MODEL", "qwen3:8b"))
        # Track the model chain so route() can fall back if the picked model fails inference.
        self._model_chain = [m for m in [_preferred, "qwen3:8b"] if m]
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

    def _rotate_model(self) -> bool:
        """Drop the current model from the chain and rebuild self.agent with the next one.

        Returns True if rotation happened, False if the chain is exhausted.
        """
        from utils.gpu_queue import select_available_model

        self._model_chain = [m for m in self._model_chain if m != self.model_name]
        if not self._model_chain:
            _router_logger.error("[Router] Model chain exhausted; no fallback available.")
            return False

        new_pref = self._model_chain[0]
        new_tail = self._model_chain[1:]
        new_model, new_host = select_available_model(new_pref, new_tail)
        _router_logger.warning(
            f"[Router] Rotating router model: '{self.model_name}' → '{new_model}' on {new_host}."
        )
        self.model_name, self.host = new_model, new_host
        self.ensure_model(self.model_name)
        self.agent = Agent(
            name="Semantic Router",
            model=Ollama(
                id=self.model_name,
                host=self.host,
                client_kwargs={"timeout": 300.0},
                options=get_ollama_options(self.model_name),
            ),
            description=self.agent.description,
            instructions=self.agent.instructions,
            show_tool_calls=False,
            json_mode=True,
        )
        return True

    def ensure_model(self, model_name: str):
        """Checks if model exists in Ollama. If not, pulls it."""
        import requests
        try:
            tags_res = requests.get(f"{self.host}/api/tags", timeout=5)
            if tags_res.status_code == 200:
                models = [m['name'] for m in tags_res.json().get('models', [])]
                if any(model_name in m for m in models):
                    return
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
        Tier-1: Keyword fast-path — returns a routing decision in <1 ms if a
        regex pattern matches, or None to fall through.
        """
        for pattern, intent, confidence in _FAST_PATH_RULES:
            if pattern.search(user_input):
                _router_logger.info(
                    f"[Router] Fast-path match: {intent} ({confidence*100:.0f}%) "
                    f"for '{user_input[:80]}'"
                )
                return {
                    "intent": intent,
                    "confidence": confidence,
                    "reasoning": f"Keyword fast-path: matched {intent} pattern",
                }
        return None

    def route(self, user_input: str) -> dict:
        """
        Three-tier classification cascade:
          1. Result cache     — instant replay for recent/identical inputs
          2. Regex fast-path  — <1 ms for unambiguous keyword signals
          3. Embedding tier   — ~10 ms cosine similarity (nomic-embed-text)
          4. LLM fallback     — 1–5 s full qwen3:8b inference (ambiguous only)
        """
        # --- Tier 1: Result cache ---
        cached = _cache_get(user_input)
        if cached:
            _router_logger.info(
                f"[Router] Cache hit: {cached.get('intent')} (confidence {cached.get('confidence', 0):.0%})"
            )
            return cached

        # --- Tier 2: Regex fast-path ---
        fast_result = self.fast_classify(user_input)
        if fast_result:
            _cache_put(user_input, fast_result)
            return fast_result

        # --- Tier 3: Embedding classifier ---
        embed_result = _embedding_classify(user_input)
        if embed_result:
            _cache_put(user_input, embed_result)
            return embed_result

        # --- Tier 4: LLM fallback ---
        _router_logger.info("[Router] No fast-path/embed match — falling back to LLM router")
        max_retries = 2

        for attempt in range(max_retries):
            try:
                if attempt == 0:
                    prompt = f"Input: {user_input}"
                else:
                    prompt = (
                        f"Input: {user_input}\n\nWARNING: Your previous classification was AMBIGUOUS "
                        "or had low confidence (< 0.6). Please re-evaluate carefully using strict logical "
                        "deduction. Ensure you provide a distinct categorization. If truly ambiguous, you "
                        "MUST provide a disambiguation_question."
                    )

                response: RunResponse = self.agent.run(prompt)

                # response.content can be a dict when phidata auto-parses JSON
                content = response.content
                if isinstance(content, dict):
                    decision = content
                else:
                    if "```json" in content:
                        content = content.replace("```json", "").replace("```", "")
                    decision = json.loads(content.strip())
                confidence = float(decision.get("confidence", 0.0))

                if confidence >= 0.75 and decision.get("intent") != "AMBIGUOUS":
                    _cache_put(user_input, decision)
                    return decision

            except Exception as e:
                error_str = str(e)
                print(f"[Router Error - Attempt {attempt+1}] {error_str}")

                # Model-chain fallback: rotate to next model if inference fails
                lowered = error_str.lower()
                retriable = (
                    "404" in error_str
                    or any(t in lowered for t in (
                        "connection", "timeout", "refused", "out of memory",
                        "cuda", "oom", "500", "unavailable",
                    ))
                )
                if retriable and self._rotate_model():
                    _router_logger.warning(
                        "[Router] Inference failure — rotated model chain; retrying."
                    )
                    continue

                if "404" in error_str and "not found" in error_str:
                    return {
                        "intent": "RESEARCH",
                        "confidence": 0.0,
                        "reasoning": f"CRITICAL: Model '{self.model_name}' missing. Please run 'ollama pull {self.model_name}'"
                    }

        if 'decision' in locals() and isinstance(decision, dict):
            _cache_put(user_input, decision)
            return decision

        return {"intent": "CONVERSATION", "confidence": 0.0, "reasoning": "Fallback Error (Router failed all retries)"}


# ---------------------------------------------------------------------------
# Global singleton (lazy-loaded)
# ---------------------------------------------------------------------------
_router_instance = None


def get_semantic_router() -> SemanticRouter:
    global _router_instance
    if _router_instance is None:
        _router_instance = SemanticRouter()
    return _router_instance
