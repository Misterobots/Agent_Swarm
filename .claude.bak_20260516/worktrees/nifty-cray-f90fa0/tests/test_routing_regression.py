"""
Phase 7: AutoAgent Routing Regression Tests

Comprehensive test suite for the SemanticRouter, dispatcher keyword classifier,
keyword overrides in the main router, and confidence cascade logic.

Tests are structured to run WITHOUT network access — all LLM calls are mocked.
"""

import json
import os
import sys
import re
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# ---------------------------------------------------------------------------
# Ensure agents/ importable (conftest.py handles this, but be explicit)
# ---------------------------------------------------------------------------
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENTS_DIR = os.path.join(REPO_ROOT, "agents")
if AGENTS_DIR not in sys.path:
    sys.path.insert(0, AGENTS_DIR)

# ---------------------------------------------------------------------------
# Pre-mock heavy third-party dependencies that are not needed for unit tests.
# This allows importing agents modules without installing the full dep tree.
# ---------------------------------------------------------------------------
_MOCK_MODULES = [
    "pynvml",
    "redis",
    "phi", "phi.agent", "phi.model", "phi.model.ollama",
    "phi.knowledge", "phi.knowledge.combined",
    "phi.vectordb", "phi.vectordb.pgvector",
    "phi.storage", "phi.storage.agent", "phi.storage.agent.postgres",
    "langfuse", "langfuse.decorators",
    "httpx",
    "pydantic",
    "requests",
    "prometheus_client",
]
for _mod in _MOCK_MODULES:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# Ensure phi.agent exposes Agent and RunResponse as usable classes
_phi_agent_mod = sys.modules["phi.agent"]
_phi_agent_mod.Agent = MagicMock
_phi_agent_mod.RunResponse = type("RunResponse", (), {"content": ""})

# Ensure phi.model.ollama exposes Ollama
_phi_ollama_mod = sys.modules["phi.model.ollama"]
_phi_ollama_mod.Ollama = MagicMock


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  FIXTURES                                                               ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

def _make_router_response(intent: str, confidence: float, reasoning: str = "",
                          disambiguation: str | None = None) -> str:
    """Build a JSON string mimicking SemanticRouter output."""
    payload = {
        "intent": intent,
        "confidence": confidence,
        "reasoning": reasoning or f"Classified as {intent}",
    }
    if disambiguation:
        payload["disambiguation_question"] = disambiguation
    return json.dumps(payload)


class FakeRunResponse:
    """Minimal stand-in for phi.agent.RunResponse."""
    def __init__(self, content: str):
        self.content = content


@pytest.fixture
def mock_ollama_env(monkeypatch):
    """Set environment so SemanticRouter doesn't hit real Ollama."""
    monkeypatch.setenv("ROUTER_MODEL", "nemotron-mini")
    monkeypatch.setenv("OLLAMA_HOST", "http://fake:11434")
    monkeypatch.setenv("PRIMARY_OLLAMA_HOST", "http://fake:11434")
    monkeypatch.setenv("SECONDARY_OLLAMA_HOST", "http://fake:11434")


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  1. DISPATCHER KEYWORD CLASSIFIER (detect_intent)                       ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

class TestDispatcherKeywordClassifier:
    """Tests for agents/dispatcher.py::detect_intent — the simple fallback."""

    def _detect(self, text: str) -> str:
        from dispatcher import detect_intent
        return detect_intent(text)

    # --- ACTION_FIGURE ---
    def test_action_figure_explicit(self):
        assert self._detect("Create an action figure of Batman") == "ACTION_FIGURE"

    def test_action_figure_posable(self):
        assert self._detect("Make a posable robot character") == "ACTION_FIGURE"

    def test_action_figure_ball_joint(self):
        assert self._detect("Generate a ball joint doll of a knight") == "ACTION_FIGURE"

    def test_action_figure_figurine(self):
        assert self._detect("I want a figurine of my cat") == "ACTION_FIGURE"

    # --- 3D ---
    def test_3d_keyword(self):
        assert self._detect("Create a 3d model of a castle") == "3D"

    def test_3d_forge(self):
        assert self._detect("Use the forge to make a dragon") == "3D"

    def test_3d_model_generate(self):
        assert self._detect("Generate a model of a spaceship") == "3D"

    # --- VISION (must be checked BEFORE IMAGE) ---
    def test_vision_what_do_you_see(self):
        assert self._detect("What do you see in this image?") == "VISION"

    def test_vision_describe_image(self):
        assert self._detect("Describe this image for me") == "VISION"

    def test_vision_analyze_image(self):
        assert self._detect("Analyze this image and tell me what's in it") == "VISION"

    def test_vision_screenshot(self):
        assert self._detect("Read this screenshot and extract the text") == "VISION"

    def test_vision_ocr(self):
        assert self._detect("Perform OCR on this document") == "VISION"

    def test_vision_whats_happening(self):
        assert self._detect("What's happening in this photo?") == "VISION"

    def test_vision_look_at_this(self):
        assert self._detect("Look at this and tell me what you think") == "VISION"

    def test_vision_identify(self):
        assert self._detect("Identify this plant in the photo") == "VISION"

    def test_vision_describe_picture(self):
        assert self._detect("Describe this picture") == "VISION"

    def test_vision_analyze_photo(self):
        assert self._detect("Analyze this photo") == "VISION"

    # --- VISION before IMAGE priority (the known misroute) ---
    def test_vision_before_image_what_see(self):
        """REGRESSION: 'what do you see in this image' must route VISION, not IMAGE."""
        result = self._detect("What do you see in this image?")
        assert result == "VISION", f"Misrouted to {result} — VISION must take priority over IMAGE"

    def test_vision_before_image_whats_in_picture(self):
        """REGRESSION: 'what is in this picture' must route VISION, not IMAGE."""
        result = self._detect("What is in this picture?")
        assert result == "VISION", f"Misrouted to {result}"

    def test_vision_before_image_whats_in_image(self):
        """REGRESSION: 'what's in this image' must route VISION, not IMAGE."""
        result = self._detect("What's in this image?")
        assert result == "VISION", f"Misrouted to {result}"

    # --- COORDINATE ---
    def test_coordinate_plan_and_build(self):
        assert self._detect("Plan and build a monitoring dashboard") == "COORDINATE"

    def test_coordinate_end_to_end(self):
        assert self._detect("Create an end-to-end CI/CD pipeline") == "COORDINATE"

    def test_coordinate_full_stack(self):
        assert self._detect("Build a full stack web application with React") == "COORDINATE"

    def test_coordinate_multi_step(self):
        assert self._detect("multi-step: research, plan, implement a new feature") == "COORDINATE"

    # --- IMAGE (only after VISION not matched) ---
    def test_image_generate(self):
        assert self._detect("Generate an image of a sunset") == "IMAGE"

    def test_image_draw(self):
        assert self._detect("Draw a portrait of a medieval knight") == "IMAGE"

    def test_image_picture_of(self):
        assert self._detect("Create a picture of a cat in space") == "IMAGE"

    def test_image_photo(self):
        assert self._detect("Take a photo of a cityscape at night") == "IMAGE"

    # --- DEFAULT ---
    def test_default_generic(self):
        assert self._detect("Hello, how are you today?") == "DEFAULT"

    def test_default_question(self):
        assert self._detect("What is the meaning of life?") == "DEFAULT"

    # --- ACTION_FIGURE takes priority over 3D ---
    def test_action_figure_over_3d(self):
        """Action figure keywords should take priority over 3D."""
        result = self._detect("Create a 3d action figure of a superhero")
        assert result == "ACTION_FIGURE", f"Got {result} — ACTION_FIGURE must override 3D"


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  2. SEMANTIC ROUTER UNIT TESTS (mocked LLM)                            ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

class TestSemanticRouterUnit:
    """Tests for agents/semantic_router.py::SemanticRouter.route() with mocked LLM."""

    def _build_router(self, responses: list[str]):
        """
        Builds a SemanticRouter with mocked internals.
        `responses` is a list of JSON strings the agent.run() will return in order.
        """
        call_idx = {"i": 0}

        def fake_run(prompt):
            idx = call_idx["i"]
            call_idx["i"] += 1
            content = responses[idx] if idx < len(responses) else responses[-1]
            return FakeRunResponse(content)

        from semantic_router import SemanticRouter
        mock_agent_instance = MagicMock()
        mock_agent_instance.run = fake_run

        router = SemanticRouter.__new__(SemanticRouter)
        router.model_name = "nemotron-mini"
        router.host = "http://fake:11434"
        router.agent = mock_agent_instance
        return router

    # --- Confident classification ---
    def test_confident_code_intent(self):
        resp = _make_router_response("CODE", 0.95, "User wants to write a Python script")
        router = self._build_router([resp])
        result = router.route("Write a Python script to sort a list")
        assert result["intent"] == "CODE"
        assert result["confidence"] >= 0.6

    def test_confident_image_intent(self):
        resp = _make_router_response("IMAGE", 0.92, "User wants visual art")
        router = self._build_router([resp])
        result = router.route("Generate an image of a dragon")
        assert result["intent"] == "IMAGE"

    def test_confident_vision_intent(self):
        resp = _make_router_response("VISION", 0.88, "User wants image analysis")
        router = self._build_router([resp])
        result = router.route("What do you see in this image?")
        assert result["intent"] == "VISION"

    def test_confident_conversation_intent(self):
        resp = _make_router_response("CONVERSATION", 0.85, "Casual greeting")
        router = self._build_router([resp])
        result = router.route("Hello, how are you?")
        assert result["intent"] == "CONVERSATION"

    def test_confident_devops_intent(self):
        resp = _make_router_response("DEVOPS", 0.91, "Infrastructure request")
        router = self._build_router([resp])
        result = router.route("Set up a Docker compose file for nginx")
        assert result["intent"] == "DEVOPS"

    def test_confident_research_intent(self):
        resp = _make_router_response("RESEARCH", 0.87, "Deep knowledge quest")
        router = self._build_router([resp])
        result = router.route("What were the main causes of the French Revolution?")
        assert result["intent"] == "RESEARCH"

    def test_confident_train_intent(self):
        resp = _make_router_response("TRAIN", 0.93, "User wants to teach the system")
        router = self._build_router([resp])
        result = router.route("Remember that my preferred language is Python")
        assert result["intent"] == "TRAIN"

    def test_confident_iot_control(self):
        resp = _make_router_response("IOT_CONTROL", 0.90, "Smart home command")
        router = self._build_router([resp])
        result = router.route("Turn on the living room lights")
        assert result["intent"] == "IOT_CONTROL"

    def test_confident_iot_dev(self):
        resp = _make_router_response("IOT_DEV", 0.88, "Firmware request")
        router = self._build_router([resp])
        result = router.route("Compile firmware for the ESP32 sensor")
        assert result["intent"] == "IOT_DEV"

    def test_confident_data_intent(self):
        resp = _make_router_response("DATA", 0.89, "Data analysis request")
        router = self._build_router([resp])
        result = router.route("Write a SQL query to aggregate monthly sales")
        assert result["intent"] == "DATA"

    def test_confident_documentation_intent(self):
        resp = _make_router_response("DOCUMENTATION", 0.86, "Writing request")
        router = self._build_router([resp])
        result = router.route("Rewrite this README in markdown format")
        assert result["intent"] == "DOCUMENTATION"

    def test_confident_3d_intent(self):
        resp = _make_router_response("3D", 0.90, "3D model request")
        router = self._build_router([resp])
        result = router.route("Create a 3D mesh of a castle tower")
        assert result["intent"] == "3D"

    def test_confident_action_figure_intent(self):
        resp = _make_router_response("ACTION_FIGURE", 0.92, "Action figure request")
        router = self._build_router([resp])
        result = router.route("Make an action figure of a samurai")
        assert result["intent"] == "ACTION_FIGURE"

    def test_confident_coordinate_intent(self):
        resp = _make_router_response("COORDINATE", 0.88, "Multi-step orchestration")
        router = self._build_router([resp])
        result = router.route("Plan and build a full monitoring stack")
        assert result["intent"] == "COORDINATE"

    # --- All 14 intents covered above ---


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  3. CONFIDENCE CASCADE & RETRY                                         ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

class TestConfidenceCascade:
    """Tests for the retry logic when confidence is < 0.6 or intent is AMBIGUOUS."""

    def _build_router(self, responses: list[str]):
        call_idx = {"i": 0}

        def fake_run(prompt):
            idx = call_idx["i"]
            call_idx["i"] += 1
            content = responses[idx] if idx < len(responses) else responses[-1]
            return FakeRunResponse(content)

        mock_agent_instance = MagicMock()
        mock_agent_instance.run = fake_run

        from semantic_router import SemanticRouter
        router = SemanticRouter.__new__(SemanticRouter)
        router.model_name = "nemotron-mini"
        router.host = "http://fake:11434"
        router.agent = mock_agent_instance
        return router

    def test_retry_on_low_confidence(self):
        """Low confidence on attempt 1 should trigger retry; accept attempt 2."""
        attempt1 = _make_router_response("CODE", 0.4, "Uncertain")
        attempt2 = _make_router_response("CODE", 0.85, "More certain after re-evaluation")
        router = self._build_router([attempt1, attempt2])
        result = router.route("Write some kind of script")
        assert result["intent"] == "CODE"
        assert result["confidence"] >= 0.6

    def test_retry_on_ambiguous(self):
        """AMBIGUOUS intent on attempt 1 should trigger retry."""
        attempt1 = _make_router_response("AMBIGUOUS", 0.7, "Unclear",
                                          disambiguation="Did you mean code or data?")
        attempt2 = _make_router_response("DATA", 0.82, "Clarified as data analysis")
        router = self._build_router([attempt1, attempt2])
        result = router.route("Process this data file")
        assert result["intent"] == "DATA"

    def test_fallback_after_all_retries_fail(self):
        """If both attempts are low-confidence, return last parsed decision."""
        attempt1 = _make_router_response("CODE", 0.3, "Very uncertain")
        attempt2 = _make_router_response("CODE", 0.4, "Still uncertain")
        router = self._build_router([attempt1, attempt2])
        result = router.route("Do something")
        # Should return last parsed decision (attempt2)
        assert result["intent"] == "CODE"
        assert result["confidence"] < 0.6

    def test_complete_failure_returns_conversation(self):
        """If all attempts raise exceptions, return CONVERSATION fallback."""
        def failing_run(prompt):
            raise Exception("Connection refused")

        mock_agent = MagicMock()
        mock_agent.run = failing_run

        from semantic_router import SemanticRouter
        router = SemanticRouter.__new__(SemanticRouter)
        router.model_name = "nemotron-mini"
        router.host = "http://fake:11434"
        router.agent = mock_agent

        result = router.route("Hello")
        assert result["intent"] == "CONVERSATION"
        assert result["confidence"] == 0.0

    def test_model_not_found_returns_research(self):
        """404 model-not-found should return RESEARCH with pull instructions."""
        def not_found_run(prompt):
            raise Exception("404 model 'nemotron-mini' not found")

        mock_agent = MagicMock()
        mock_agent.run = not_found_run

        from semantic_router import SemanticRouter
        router = SemanticRouter.__new__(SemanticRouter)
        router.model_name = "nemotron-mini"
        router.host = "http://fake:11434"
        router.agent = mock_agent

        result = router.route("Test input")
        assert result["intent"] == "RESEARCH"
        assert "missing" in result["reasoning"].lower() or "pull" in result["reasoning"].lower()

    def test_json_wrapped_in_markdown(self):
        """Router should handle JSON wrapped in ```json``` fences."""
        raw = '```json\n' + _make_router_response("DEVOPS", 0.91, "Docker request") + '\n```'
        router = self._build_router([raw])
        result = router.route("Set up Docker")
        assert result["intent"] == "DEVOPS"

    def test_retry_prompt_contains_warning(self):
        """On retry, the prompt should contain a WARNING about low confidence."""
        prompts_seen = []

        def spying_run(prompt):
            prompts_seen.append(prompt)
            # First call: low confidence. Second call: high confidence.
            if len(prompts_seen) == 1:
                return FakeRunResponse(_make_router_response("CODE", 0.3, "Unsure"))
            return FakeRunResponse(_make_router_response("CODE", 0.85, "Confident now"))

        mock_agent = MagicMock()
        mock_agent.run = spying_run

        from semantic_router import SemanticRouter
        router = SemanticRouter.__new__(SemanticRouter)
        router.model_name = "nemotron-mini"
        router.host = "http://fake:11434"
        router.agent = mock_agent

        router.route("Some ambiguous input")

        assert len(prompts_seen) == 2
        assert "WARNING" in prompts_seen[1]


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  4. KEYWORD OVERRIDES IN MAIN ROUTER (church.py chat_swarm)            ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

class TestKeywordOverrides:
    """Tests for keyword overrides that happen AFTER the neural router in chat_swarm."""

    def test_train_override_from_learn_prefix(self):
        """'learn:' prefix should force TRAIN intent regardless of neural output."""
        from church import _is_explicit_train_request
        assert _is_explicit_train_request("learn: always use tabs for indentation") is True

    def test_train_override_from_correction(self):
        from church import _is_explicit_train_request
        assert _is_explicit_train_request("correction: the API endpoint is /v2 not /v1") is True

    def test_train_override_from_remember_that(self):
        from church import _is_explicit_train_request
        assert _is_explicit_train_request("Remember that I prefer dark themes") is True

    def test_train_override_from_remember_this_rule(self):
        from church import _is_explicit_train_request
        assert _is_explicit_train_request("Remember this rule: no semicolons in JS") is True

    def test_train_override_store_rule(self):
        from church import _is_explicit_train_request
        assert _is_explicit_train_request("Store this rule: always use TypeScript") is True

    def test_train_override_add_rule(self):
        from church import _is_explicit_train_request
        assert _is_explicit_train_request("Add rule: use 2 spaces indentation") is True

    def test_not_train_normal_question(self):
        from church import _is_explicit_train_request
        assert _is_explicit_train_request("How do I learn Python?") is False

    def test_not_train_correction_midsentence(self):
        from church import _is_explicit_train_request
        assert _is_explicit_train_request("I need a correction on this code") is False

    def test_teach_pattern_means(self):
        from church import _is_explicit_train_request
        assert _is_explicit_train_request("Remember that TypeScript means typed JavaScript") is True

    def test_teach_pattern_should_be(self):
        from church import _is_explicit_train_request
        assert _is_explicit_train_request("Correction: API version should be v3") is True


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  5. VISION vs IMAGE REGRESSION (the critical misroute)                 ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

class TestVisionImageRegression:
    """
    REGRESSION TESTS for the known VISION↔IMAGE misroute.

    The neural router sometimes misclassifies image analysis requests
    as image generation. The dispatcher keyword fallback handles this
    correctly. These tests verify both layers.
    """

    def _detect(self, text: str) -> str:
        from dispatcher import detect_intent
        return detect_intent(text)

    # --- Image ANALYSIS (should be VISION) ---
    def test_what_do_you_see(self):
        assert self._detect("What do you see in this image?") == "VISION"

    def test_describe_this_image(self):
        assert self._detect("Describe this image") == "VISION"

    def test_analyze_this_image(self):
        assert self._detect("Analyze this image") == "VISION"

    def test_what_is_in_this_picture(self):
        assert self._detect("What is in this picture?") == "VISION"

    def test_read_screenshot(self):
        assert self._detect("Read this screenshot") == "VISION"

    def test_whats_happening_in_photo(self):
        assert self._detect("What's happening in this photo?") == "VISION"

    def test_identify_object(self):
        assert self._detect("Identify this object in the image") == "VISION"

    # --- Image GENERATION (should be IMAGE) ---
    def test_generate_image(self):
        assert self._detect("Generate an image of a sunset over mountains") == "IMAGE"

    def test_draw_portrait(self):
        assert self._detect("Draw a portrait of a medieval knight") == "IMAGE"

    def test_create_picture(self):
        assert self._detect("Create a picture of a cat in space") == "IMAGE"

    # --- Edge cases: ambiguous phrasing ---
    def test_look_at_this_is_vision(self):
        """'look at this' implies the user wants analysis, not generation."""
        assert self._detect("Look at this photo and describe what you see") == "VISION"

    def test_make_image_is_generation(self):
        """'make an image' is clearly generation."""
        assert self._detect("Make an image of a cyberpunk city") == "IMAGE"


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  6. CONSTRAINT CONTEXT EXTRACTION                                      ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

class TestConstraintContext:
    """Tests for _extract_constraint_context in church.py."""

    def test_extracts_constraint_keywords(self):
        from church import _extract_constraint_context
        history = [
            {"role": "user", "content": "We have a constraint: no downtime allowed"},
            {"role": "assistant", "content": "Understood."},
            {"role": "user", "content": "Deploy the new version"},
        ]
        result = _extract_constraint_context(history, "Deploy now")
        assert "no downtime" in result.lower()
        assert "[Active User Constraints" in result

    def test_extracts_must_keyword(self):
        from church import _extract_constraint_context
        history = [
            {"role": "user", "content": "The deployment must happen during the maintenance window at 2am"},
        ]
        result = _extract_constraint_context(history, "Go ahead")
        assert "maintenance window" in result.lower()

    def test_ignores_assistant_messages(self):
        from church import _extract_constraint_context
        history = [
            {"role": "assistant", "content": "You must follow this constraint"},
            {"role": "user", "content": "Generate a report"},
        ]
        # Assistant messages are ignored, and "Generate a report" has no constraint keywords
        result = _extract_constraint_context(history, "")
        assert result == ""

    def test_empty_history_returns_empty(self):
        from church import _extract_constraint_context
        assert _extract_constraint_context(None, "test") == ""
        assert _extract_constraint_context([], "test") == ""

    def test_limits_to_recent_constraints(self):
        from church import _extract_constraint_context
        history = [
            {"role": "user", "content": f"Constraint {i}: requirement {i}"} for i in range(10)
        ]
        result = _extract_constraint_context(history, "deploy")
        # Should only contain the 3 most recent (indices 7, 8, 9)
        assert "requirement 9" in result
        assert "requirement 8" in result
        assert "requirement 7" in result
        # Older constraints should be dropped
        assert "requirement 0" not in result


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  7. INTENT CAPABILITIES MAPPING                                        ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

class TestIntentCapabilities:
    """Tests for agents/intent_capabilities.py mapping intents to agent profiles."""

    def test_image_intent_maps_to_art_director(self):
        from intent_capabilities import INTENT_CAPABILITY_MAP
        profile = INTENT_CAPABILITY_MAP["IMAGE"]
        assert profile["agent_name"] == "Art Director"
        assert "image_generate" in profile["capabilities"]

    def test_3d_intent_maps_correctly(self):
        from intent_capabilities import INTENT_CAPABILITY_MAP
        profile = INTENT_CAPABILITY_MAP["3D"]
        assert profile["template_id"] == "3d_creator"
        assert "file_write" in profile["capabilities"]

    def test_action_figure_intent_maps_correctly(self):
        from intent_capabilities import INTENT_CAPABILITY_MAP
        profile = INTENT_CAPABILITY_MAP["ACTION_FIGURE"]
        assert profile["template_id"] == "action_figure_creator"

    def test_code_intent_exists(self):
        from intent_capabilities import INTENT_CAPABILITY_MAP
        assert "CODE" in INTENT_CAPABILITY_MAP

    def test_vision_intent_exists(self):
        from intent_capabilities import INTENT_CAPABILITY_MAP
        assert "VISION" in INTENT_CAPABILITY_MAP

    def test_coordinate_intent_exists(self):
        from intent_capabilities import INTENT_CAPABILITY_MAP
        assert "COORDINATE" in INTENT_CAPABILITY_MAP

    def test_capability_mapped_intents(self):
        """All intents that have agent profiles should be present."""
        from intent_capabilities import INTENT_CAPABILITY_MAP
        expected_mapped = {
            "CODE", "IMAGE", "3D", "ACTION_FIGURE", "RESEARCH",
            "DOCUMENTATION", "TRAIN", "IOT_CONTROL", "IOT_DEV",
            "VISION", "COORDINATE",
        }
        assert expected_mapped.issubset(set(INTENT_CAPABILITY_MAP.keys())), \
            f"Missing intents: {expected_mapped - set(INTENT_CAPABILITY_MAP.keys())}"

    def test_default_capabilities_for_unknown(self):
        """Unknown/AMBIGUOUS intents should get safe defaults via get_capabilities_for_intent."""
        from intent_capabilities import get_capabilities_for_intent
        profile = get_capabilities_for_intent("UNKNOWN_INTENT")
        assert profile["agent_name"] == "Router"
        assert profile["security_level"] == "L1_PUBLIC"

    def test_all_profiles_have_required_keys(self):
        from intent_capabilities import INTENT_CAPABILITY_MAP
        required_keys = {"agent_name", "template_id", "capabilities", "security_level"}
        for intent, profile in INTENT_CAPABILITY_MAP.items():
            for key in required_keys:
                assert key in profile, f"Intent {intent} missing key '{key}'"


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  8. SKILL HINT & RESEARCH MODE OVERRIDES                               ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

class TestSkillAndModeOverrides:
    """Tests for skill hint override and research mode override logic in church.py."""

    def test_skill_hint_mapping_keys(self):
        """Verify the skill-to-intent mapping dictionary."""
        _skill_to_intent = {
            "code": "DEVOPS",
            "devops": "DEVOPS",
            "data": "DATA",
            "creative": "IMAGE",
            "research": "RESEARCH",
        }
        assert _skill_to_intent["code"] == "DEVOPS"
        assert _skill_to_intent["creative"] == "IMAGE"
        assert _skill_to_intent["research"] == "RESEARCH"

    def test_train_downgrade_without_explicit_prefix(self):
        """TRAIN intent from neural router should downgrade to CONVERSATION
        if the input lacks explicit training prefixes."""
        from church import _is_explicit_train_request
        # "How do I train a model?" is NOT an explicit training directive
        assert _is_explicit_train_request("How do I train a model?") is False
        # But "Remember that..." IS explicit
        assert _is_explicit_train_request("Remember that I prefer Python") is True


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  9. ENSURE_MODEL SELF-HEALING                                          ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

class TestEnsureModel:
    """Tests for SemanticRouter.ensure_model() self-healing logic."""

    def test_model_exists_no_pull(self):
        """If model exists in tags, no pull should be attempted."""
        with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
            mock_tags_resp = MagicMock()
            mock_tags_resp.status_code = 200
            mock_tags_resp.json.return_value = {
                "models": [{"name": "nemotron-mini:latest"}]
            }
            mock_get.return_value = mock_tags_resp

            from semantic_router import SemanticRouter
            router = SemanticRouter.__new__(SemanticRouter)
            router.host = "http://fake:11434"
            router.ensure_model("nemotron-mini")

            mock_post.assert_not_called()

    def test_model_missing_triggers_pull(self):
        """If model is not in tags, it should attempt to pull."""
        with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
            mock_tags_resp = MagicMock()
            mock_tags_resp.status_code = 200
            mock_tags_resp.json.return_value = {"models": []}
            mock_get.return_value = mock_tags_resp

            mock_pull_resp = MagicMock()
            mock_pull_resp.status_code = 200
            mock_post.return_value = mock_pull_resp

            from semantic_router import SemanticRouter
            router = SemanticRouter.__new__(SemanticRouter)
            router.host = "http://fake:11434"
            router.ensure_model("nemotron-mini")

            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "api/pull" in call_args[0][0]

    def test_connection_error_graceful(self):
        """Network errors in ensure_model should not raise — just print warning."""
        with patch("requests.get") as mock_get:
            mock_get.side_effect = Exception("Connection refused")

            from semantic_router import SemanticRouter
            router = SemanticRouter.__new__(SemanticRouter)
            router.host = "http://fake:11434"
            # Should not raise
            router.ensure_model("nemotron-mini")
