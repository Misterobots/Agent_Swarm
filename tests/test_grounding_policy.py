"""Focused regression tests for live-information grounding policy."""
from handlers.base import _needs_web_grounding


def test_current_model_hardware_recommendations_require_web_grounding():
    queries = [
        "Recommend the current Qwen models for 8GB and 16GB VRAM",
        "Which Ollama model is compatible with my GPU?",
        "What are the newest Llama variants?",
        "Give me the 2026 Gemma catalog",
    ]
    assert all(_needs_web_grounding(query) for query in queries)


def test_stable_conceptual_queries_do_not_force_web_grounding():
    queries = [
        "Explain transformer attention",
        "Show a matrix multiplication example",
        "What is quantization in general?",
        "How does a context window work?",
    ]
    assert not any(_needs_web_grounding(query) for query in queries)


def test_keyword_matching_uses_word_boundaries():
    assert not _needs_web_grounding("Explain a knowledge graph")
