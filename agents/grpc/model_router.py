"""
model_router.py — Intent → Model → Node routing for OpenClaude gRPC server.

Pure Python module with no gRPC dependency.  Maps user prompts through
intent classification to the optimal (model, Ollama node) pair, then
executes inference via Ollama's HTTP API.

Model assignments (from config.py):
    nemotron-orchestrator:8b → intent classification (router)
    qwen2.5-coder:14b      → code generation
    qwen3:14b              → general reasoning
    llama3.2:3b            → research / lightweight tasks
    moondream:latest       → vision (image analysis)
"""

import logging
import os
import time
import requests
from dataclasses import dataclass, field
from typing import Dict, Generator, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (read from env, with defaults matching config.py)
# ---------------------------------------------------------------------------
ROUTER_MODEL = os.getenv("ROUTER_MODEL", "nemotron-orchestrator:8b")
CODE_MODEL = os.getenv("ARCHITECT_MODEL", "qwen2.5-coder:14b-instruct-q4_k_m")
GENERAL_MODEL = os.getenv("COORDINATOR_MODEL", "qwen3:14b")
RESEARCH_MODEL = os.getenv("LIBRARIAN_MODEL", "llama3.2:3b")
VISION_MODEL = os.getenv("VISION_MODEL", "moondream:latest")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
SECONDARY_OLLAMA_HOST = os.getenv("SECONDARY_OLLAMA_HOST", "http://192.168.2.103:11434")

OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))

# ---------------------------------------------------------------------------
# Intent-to-Model mapping
# ---------------------------------------------------------------------------
INTENT_MODEL_MAP: Dict[str, str] = {
    "CODE": CODE_MODEL,
    "GENERAL": GENERAL_MODEL,
    "DEFAULT": GENERAL_MODEL,
    "RESEARCH": RESEARCH_MODEL,
    "VISION": VISION_MODEL,
    "IMAGE": GENERAL_MODEL,       # image prompts still route to general for description
    "3D": GENERAL_MODEL,
    "COORDINATE": GENERAL_MODEL,
}

# Model role labels (for ListModels response)
MODEL_ROLES: Dict[str, str] = {
    ROUTER_MODEL: "router",
    CODE_MODEL: "code",
    GENERAL_MODEL: "general",
    RESEARCH_MODEL: "research",
    VISION_MODEL: "vision",
}

# Context windows (duplicated here for standalone operation on R730)
CONTEXT_WINDOWS: Dict[str, int] = {
    "qwen2.5-coder:14b": 32768,
    "qwen2.5-coder:14b-instruct-q4_k_m": 32768,
    "qwen3:14b": 40960,
    "nemotron-orchestrator:8b": 32768,
    "nemotron-mini": 4096,
    "llama3.2:3b": 8192,
    "moondream:latest": 2048,
    "default": 8192,
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class InferenceResult:
    """Result of a model inference call."""
    content: str
    model_used: str
    node: str
    tokens_used: int = 0
    duration_ms: float = 0.0
    intent_detected: str = ""
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "model_used": self.model_used,
            "node": self.node,
            "tokens_used": self.tokens_used,
            "duration_ms": self.duration_ms,
            "intent_detected": self.intent_detected,
            "error": self.error,
        }


@dataclass
class ClassificationResult:
    """Result of intent classification."""
    intent: str
    confidence: float
    suggested_model: str
    suggested_node: str

    def to_dict(self) -> dict:
        return {
            "intent": self.intent,
            "confidence": self.confidence,
            "suggested_model": self.suggested_model,
            "suggested_node": self.suggested_node,
        }


@dataclass
class ModelStatus:
    """Status of a model on a specific node."""
    name: str
    role: str
    context_window: int
    available: bool
    node: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "role": self.role,
            "context_window": self.context_window,
            "available": self.available,
            "node": self.node,
        }


@dataclass
class NodeHealth:
    """Cached health status for an Ollama node."""
    host: str
    name: str
    healthy: bool = False
    available_models: List[str] = field(default_factory=list)
    last_checked: float = 0.0


# ---------------------------------------------------------------------------
# Model Router
# ---------------------------------------------------------------------------
HEALTH_CACHE_TTL = 30  # seconds


class ModelRouter:
    """
    Routes inference requests to the optimal (model, node) pair.

    Flow:
        1. If explicit model given → find node with that model
        2. If intent given → map to model via INTENT_MODEL_MAP
        3. If neither → classify intent via nemotron-orchestrator:8b, then route
    """

    def __init__(
        self,
        ollama_hosts: Optional[List[str]] = None,
        intent_model_map: Optional[Dict[str, str]] = None,
        router_model: Optional[str] = None,
    ):
        self._hosts = ollama_hosts or [OLLAMA_HOST, SECONDARY_OLLAMA_HOST]
        # De-duplicate and filter empties
        seen = set()
        unique = []
        for h in self._hosts:
            if h and h not in seen:
                seen.add(h)
                unique.append(h)
        self._hosts = unique

        self._intent_map = intent_model_map or INTENT_MODEL_MAP
        self._router_model = router_model or ROUTER_MODEL
        self._node_cache: Dict[str, NodeHealth] = {}
        self._start_time = time.time()

    # ----- Public API -----

    def classify_intent(self, prompt: str) -> ClassificationResult:
        """
        Classify the intent of a prompt using the router model (nemotron-orchestrator:8b).
        Returns the detected intent, confidence, and suggested model + node.
        """
        classification_prompt = (
            "Classify the following user request into exactly ONE category. "
            "Categories: CODE, GENERAL, RESEARCH, VISION, IMAGE, 3D, COORDINATE. "
            "Reply with ONLY the category name, nothing else.\n\n"
            f"Request: {prompt}"
        )

        host = self._find_host_for_model(self._router_model)
        if not host:
            # Fallback: return GENERAL if router model unavailable
            logger.warning(f"Router model {self._router_model} not available on any node")
            model = self._intent_map.get("GENERAL", GENERAL_MODEL)
            node = self._hosts[0] if self._hosts else "unknown"
            return ClassificationResult(
                intent="GENERAL", confidence=0.5,
                suggested_model=model, suggested_node=node,
            )

        try:
            resp = self._call_ollama(host, self._router_model, classification_prompt)
            raw_intent = resp.strip().upper()

            # Normalize: extract first word that matches a known intent
            intent = "GENERAL"
            for candidate in self._intent_map:
                if candidate in raw_intent:
                    intent = candidate
                    break

            model = self._intent_map.get(intent, GENERAL_MODEL)
            node = self._find_host_for_model(model) or host
            confidence = 0.9 if intent != "GENERAL" else 0.7

            return ClassificationResult(
                intent=intent, confidence=confidence,
                suggested_model=model, suggested_node=node,
            )
        except Exception as e:
            logger.error(f"Intent classification failed: {e}")
            model = self._intent_map.get("GENERAL", GENERAL_MODEL)
            return ClassificationResult(
                intent="GENERAL", confidence=0.3,
                suggested_model=model, suggested_node=host,
            )

    def infer(
        self,
        prompt: str,
        model: str = "",
        intent: str = "",
        max_tokens: int = 0,
        temperature: float = 0.7,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> InferenceResult:
        """
        Run synchronous inference. Auto-routes if model/intent not specified.
        """
        start = time.time()
        detected_intent = intent

        # Step 1: Resolve model
        if not model:
            if intent and intent in self._intent_map:
                model = self._intent_map[intent]
            else:
                classification = self.classify_intent(prompt)
                model = classification.suggested_model
                detected_intent = classification.intent

        # Step 2: Find best host
        host = self._find_host_for_model(model)
        if not host:
            # Fallback to first healthy host with any model
            host = self._get_any_healthy_host()
            if not host:
                return InferenceResult(
                    content="", model_used=model, node="none",
                    error="No healthy Ollama nodes available",
                    intent_detected=detected_intent,
                )

        # Step 3: Build messages
        messages = []
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        # Step 4: Call Ollama
        try:
            content = self._call_ollama_chat(
                host, model, messages,
                max_tokens=max_tokens, temperature=temperature,
            )
            duration = (time.time() - start) * 1000

            return InferenceResult(
                content=content,
                model_used=model,
                node=host,
                duration_ms=round(duration, 2),
                intent_detected=detected_intent,
            )
        except Exception as e:
            duration = (time.time() - start) * 1000
            logger.error(f"Inference failed on {host} with {model}: {e}")
            return InferenceResult(
                content="", model_used=model, node=host,
                duration_ms=round(duration, 2),
                error=str(e),
                intent_detected=detected_intent,
            )

    def infer_stream(
        self,
        prompt: str,
        model: str = "",
        intent: str = "",
        max_tokens: int = 0,
        temperature: float = 0.7,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Generator[Dict, None, None]:
        """
        Run streaming inference. Yields dicts with 'content', 'done', 'model_used'.
        """
        detected_intent = intent

        # Resolve model
        if not model:
            if intent and intent in self._intent_map:
                model = self._intent_map[intent]
            else:
                classification = self.classify_intent(prompt)
                model = classification.suggested_model
                detected_intent = classification.intent

        # Find host
        host = self._find_host_for_model(model)
        if not host:
            host = self._get_any_healthy_host()
            if not host:
                yield {"content": "Error: No healthy Ollama nodes", "done": True, "model_used": model}
                return

        # Build messages
        messages = []
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        # Stream from Ollama
        try:
            payload = {
                "model": model,
                "messages": messages,
                "stream": True,
            }
            if max_tokens > 0:
                payload["options"] = {"num_predict": max_tokens, "temperature": temperature}
            elif temperature != 0.7:
                payload["options"] = {"temperature": temperature}

            resp = requests.post(
                f"{host}/api/chat",
                json=payload,
                stream=True,
                timeout=OLLAMA_TIMEOUT,
            )
            resp.raise_for_status()

            import json
            for line in resp.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                msg = chunk.get("message", {})
                done = chunk.get("done", False)
                yield {
                    "content": msg.get("content", ""),
                    "done": done,
                    "model_used": model,
                    "tokens_used": chunk.get("eval_count", 0) if done else 0,
                }
                if done:
                    return

        except Exception as e:
            logger.error(f"Streaming inference failed: {e}")
            yield {"content": f"Error: {e}", "done": True, "model_used": model}

    def list_models(self) -> List[ModelStatus]:
        """List all configured models with availability status."""
        models = []
        for host in self._hosts:
            health = self._check_node(host)
            for model_name, role in MODEL_ROLES.items():
                available = model_name in health.available_models or any(
                    model_name in m for m in health.available_models
                )
                ctx = CONTEXT_WINDOWS.get(model_name, CONTEXT_WINDOWS.get("default", 8192))
                models.append(ModelStatus(
                    name=model_name,
                    role=role,
                    context_window=ctx,
                    available=available,
                    node=host,
                ))
        return models

    def health_check(self) -> Tuple[str, Dict[str, bool], int]:
        """
        Check health of all nodes.
        Returns (status, node_health_map, models_available_count).
        """
        node_health = {}
        total_models = 0
        for host in self._hosts:
            health = self._check_node(host, force=True)
            node_health[host] = health.healthy
            if health.healthy:
                total_models += len(health.available_models)

        healthy_count = sum(1 for v in node_health.values() if v)
        if healthy_count == len(self._hosts):
            status = "healthy"
        elif healthy_count > 0:
            status = "degraded"
        else:
            status = "unhealthy"

        return status, node_health, total_models

    @property
    def uptime_seconds(self) -> int:
        return int(time.time() - self._start_time)

    # ----- Private helpers -----

    def _find_host_for_model(self, model: str) -> Optional[str]:
        """Find the first healthy host that has the specified model."""
        for host in self._hosts:
            health = self._check_node(host)
            if not health.healthy:
                continue
            # Check exact match or prefix match
            for avail in health.available_models:
                if model == avail or model in avail or avail in model:
                    return host
        return None

    def _get_any_healthy_host(self) -> Optional[str]:
        """Get any healthy host as fallback."""
        for host in self._hosts:
            health = self._check_node(host)
            if health.healthy:
                return host
        return None

    def _check_node(self, host: str, force: bool = False) -> NodeHealth:
        """Check node health with TTL caching."""
        cached = self._node_cache.get(host)
        now = time.time()

        if cached and not force and (now - cached.last_checked) < HEALTH_CACHE_TTL:
            return cached

        health = NodeHealth(host=host, name=host)
        try:
            resp = requests.get(f"{host}/api/tags", timeout=3)
            if resp.status_code == 200:
                models_data = resp.json().get("models", [])
                health.available_models = [m.get("name", "") for m in models_data]
                health.healthy = True
            health.last_checked = now
        except Exception:
            health.last_checked = now
            logger.debug(f"Node {host} health check failed")

        self._node_cache[host] = health
        return health

    def _call_ollama(self, host: str, model: str, prompt: str) -> str:
        """Call Ollama generate API (non-chat, for classification)."""
        resp = requests.post(
            f"{host}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("response", "")

    def _call_ollama_chat(
        self, host: str, model: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 0, temperature: float = 0.7,
    ) -> str:
        """Call Ollama chat API."""
        payload: Dict = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        options: Dict = {}
        if max_tokens > 0:
            options["num_predict"] = max_tokens
        if temperature != 0.7:
            options["temperature"] = temperature
        if options:
            payload["options"] = options

        resp = requests.post(
            f"{host}/api/chat",
            json=payload,
            timeout=OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "")


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_router_instance: Optional[ModelRouter] = None


def get_model_router() -> ModelRouter:
    global _router_instance
    if _router_instance is None:
        _router_instance = ModelRouter()
    return _router_instance
