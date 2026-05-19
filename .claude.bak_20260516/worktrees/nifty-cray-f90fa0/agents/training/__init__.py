"""
Training Pipeline for MarsRL / ToolOrchestra GRPO fine-tuning.

Modules:
  - export_traces: Langfuse → GRPO JSONL export
  - synthetic_gen: ToolScale-style synthetic trajectory generation
  - reward_function: Multi-objective reward for GRPO training
  - grpo_trainer: QLoRA GRPO training wrapper (Phase 2)
  - convert_gguf: LoRA merge + GGUF conversion + Ollama import (Phase 2)
  - ab_test: A/B testing harness for model lifecycle (Phase 3)
"""
