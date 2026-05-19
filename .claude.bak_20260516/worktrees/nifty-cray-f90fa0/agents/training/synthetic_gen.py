"""
ToolScale-style synthetic trajectory generator.

Generates diverse multi-turn tool-use problems for the local
Hive tool set, runs them through the solver + verifier to get
scored trajectories, and outputs GRPO-compatible JSONL.

Per ToolOrchestra findings, ~552 high-quality problems are
sufficient for significant GRPO training improvement.

Usage:
    python -m training.synthetic_gen --target 100 --output training_data/synthetic.jsonl
"""

import json
import os
import sys
import random
import logging
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import OLLAMA_HOST, SECONDARY_OLLAMA_HOST, ARCHITECT_MODEL
from training.reward_function import MarsRewardFunction

logger = logging.getLogger("SyntheticGen")

# ---------------------------------------------------------------------------
# Tool definitions (mirrors agents/tools/)
# ---------------------------------------------------------------------------
TOOL_DEFINITIONS = [
    {
        "name": "read_file",
        "params": {"path": "string"},
        "description": "Read contents of a file at the given path",
    },
    {
        "name": "write_file",
        "params": {"path": "string", "content": "string"},
        "description": "Write content to a file, creating it if needed",
    },
    {
        "name": "list_dir",
        "params": {"path": "string"},
        "description": "List files and directories at the given path",
    },
    {
        "name": "run_command",
        "params": {"command": "string"},
        "description": "Execute a shell command and return output",
    },
]

# ---------------------------------------------------------------------------
# Task templates by domain
# ---------------------------------------------------------------------------
CODE_TASKS = [
    "Write a Python function that {action}",
    "Create a Python script that reads {input_type} and outputs {output_type}",
    "Write a {language} class that implements {pattern}",
    "Debug and fix this Python code that should {expected} but instead {actual}:\n```python\n{code}\n```",
    "Refactor this function to be more efficient:\n```python\n{code}\n```",
    "Write unit tests for a function that {action}",
    "Create a REST API endpoint that {action} using FastAPI",
    "Write a data processing pipeline that {action}",
]

FILE_TASKS = [
    "Read the config file at {path} and extract the value of {key}",
    "Create a new {filetype} file at {path} with {content_desc}",
    "List all {extension} files in the {directory} directory",
    "Update the {key} field in {path} from {old_val} to {new_val}",
]

IOT_TASKS = [
    "Turn {state} the {device} in the {room}",
    "Set the {device} in {room} to {value}",
    "Check the current status of all {device_type} devices",
    "Create an automation that {trigger} then {action}",
]

RESEARCH_TASKS = [
    "Explain how {concept} works in the context of {domain}",
    "Compare and contrast {thing_a} and {thing_b} for {use_case}",
    "What are the best practices for {topic} in {context}?",
    "Summarize the key points of {subject}",
]

# Filler values for template expansion
ACTIONS = [
    "sorts a list of dictionaries by a nested key",
    "validates email addresses using regex",
    "calculates the Fibonacci sequence iteratively",
    "converts CSV to JSON format",
    "implements a simple LRU cache",
    "parses command-line arguments",
    "creates a TCP echo server",
    "generates random passwords with configurable complexity",
    "implements binary search on a sorted array",
    "compresses and decompresses text using gzip",
    "merges two sorted linked lists",
    "implements a rate limiter using token bucket algorithm",
    "reads environment variables and validates required ones",
    "creates a simple pub/sub event system",
    "implements retry logic with exponential backoff",
]

LANGUAGES = ["Python", "TypeScript", "JavaScript"]
PATTERNS = [
    "the Observer pattern", "a Singleton", "a Builder pattern",
    "an async iterator", "a context manager", "a decorator factory",
]
DEVICES = ["lights", "thermostat", "fan", "smart plug", "speaker"]
ROOMS = ["living room", "bedroom", "kitchen", "office", "garage"]
CONCEPTS = [
    "GRPO training", "LoRA fine-tuning", "vector embeddings",
    "attention mechanisms", "SPIFFE/SPIRE workload identity",
    "SSE streaming", "WebSocket protocols", "Docker networking",
]


class SyntheticTrajectoryGenerator:
    """Generate synthetic multi-turn trajectories for GRPO training."""

    def __init__(
        self,
        solver_host: str = OLLAMA_HOST,
        solver_model: str = ARCHITECT_MODEL,
        output_dir: str = "training_data",
    ):
        self.solver_host = solver_host
        self.solver_model = solver_model
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.reward_fn = MarsRewardFunction()

    def generate_task(self, domain: Optional[str] = None) -> dict:
        """Generate a random task from templates."""
        if domain is None:
            domain = random.choice(["code", "code", "code", "file", "iot", "research"])

        if domain == "code":
            template = random.choice(CODE_TASKS)
            task = template.format(
                action=random.choice(ACTIONS),
                input_type=random.choice(["a CSV file", "JSON data", "user input", "an API response"]),
                output_type=random.choice(["formatted JSON", "a summary report", "a sorted list", "a filtered dataset"]),
                language=random.choice(LANGUAGES),
                pattern=random.choice(PATTERNS),
                expected="sort items by date",
                actual="raises a TypeError on None values",
                code="def process(items):\n    return sorted(items, key=lambda x: x['date'])",
            )
        elif domain == "file":
            template = random.choice(FILE_TASKS)
            task = template.format(
                path=random.choice(["/app/config.yaml", "settings.json", "data/input.csv"]),
                key=random.choice(["database_url", "api_key", "max_retries", "log_level"]),
                filetype=random.choice(["YAML", "JSON", "TOML"]),
                content_desc="default application configuration",
                extension=random.choice([".py", ".ts", ".json", ".yaml"]),
                directory=random.choice(["src", "config", "tests"]),
                old_val="localhost",
                new_val="192.168.2.102",
            )
        elif domain == "iot":
            template = random.choice(IOT_TASKS)
            task = template.format(
                state=random.choice(["on", "off"]),
                device=random.choice(DEVICES),
                room=random.choice(ROOMS),
                value=random.choice(["72°F", "50%", "warm white"]),
                device_type=random.choice(["light", "climate", "switch"]),
                trigger=random.choice(["sunset", "motion detected", "temperature > 80°F"]),
                action=random.choice(["dim lights to 30%", "turn on the fan", "send a notification"]),
            )
        else:
            template = random.choice(RESEARCH_TASKS)
            task = template.format(
                concept=random.choice(CONCEPTS),
                domain=random.choice(["distributed systems", "machine learning", "home automation"]),
                thing_a=random.choice(["Redis", "PostgreSQL", "SQLite"]),
                thing_b=random.choice(["MongoDB", "DynamoDB", "ClickHouse"]),
                use_case=random.choice(["real-time analytics", "session storage", "vector search"]),
                topic=random.choice(["API design", "error handling", "logging"]),
                context=random.choice(["microservices", "Python applications", "React frontends"]),
                subject=random.choice(["transformer architecture", "RLHF training", "zero-trust security"]),
            )

        return {"task": task, "domain": domain}

    def generate_trajectory(self, task_desc: str, domain: str) -> Optional[dict]:
        """
        Generate a single trajectory by sending the task to the solver
        via Ollama API and formatting the response.
        """
        # Use longer timeout for first request (cold model loading can take minutes)
        timeout = 300 if not hasattr(self, "_model_warm") else 120
        try:
            resp = requests.post(
                f"{self.solver_host}/api/generate",
                json={
                    "model": self.solver_model,
                    "prompt": task_desc,
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 2048},
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            result = resp.json()
            response_text = result.get("response", "")
            self._model_warm = True  # Model is loaded after first success
        except Exception as e:
            logger.warning(f"Solver generation failed: {e}")
            return None

        if not response_text or len(response_text) < 20:
            return None

        # Simple quality heuristic (mirrors verifier logic)
        score = self._heuristic_score(response_text, domain)
        if score < 0.6:
            return None

        reward = self.reward_fn.compute_reward(
            final_score=score,
            iterations=1,
            safety_passed=True,
        )

        trajectory_id = f"synthetic_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{random.randint(1000, 9999)}"

        return {
            "id": trajectory_id,
            "conversations": [
                {"role": "user", "content": task_desc},
                {"role": "assistant", "content": response_text},
            ],
            "reward": {
                "correctness": reward.correctness,
                "efficiency": reward.efficiency,
                "safety": reward.safety,
                "composite": reward.composite,
            },
            "metadata": {
                "domain": domain,
                "source": "synthetic",
                "model": self.solver_model,
                "generated_at": datetime.utcnow().isoformat(),
            },
        }

    def _heuristic_score(self, response: str, domain: str) -> float:
        """Quick quality score without running full verifier."""
        score = 1.0

        # Length check
        if len(response) < 50:
            score -= 0.4

        # Repetition check
        lines = response.strip().split("\n")
        if len(lines) > 5:
            unique_ratio = len(set(lines)) / len(lines)
            if unique_ratio < 0.5:
                score -= 0.4

        # Code-specific checks
        if domain == "code":
            has_code = "```" in response or "def " in response or "class " in response
            if not has_code:
                score -= 0.2

        # Truncation check
        if response.rstrip().endswith("...") or response.count("```") % 2 != 0:
            score -= 0.3

        return max(0.0, score)

    def generate_dataset(
        self,
        target_count: int = 552,
        output_path: Optional[str] = None,
        max_attempts: int = 0,
    ) -> int:
        """
        Generate synthetic trajectories until target_count high-quality ones.
        """
        if output_path is None:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            output_path = str(self.output_dir / f"synthetic_{timestamp}.jsonl")

        if max_attempts <= 0:
            max_attempts = target_count * 3

        generated = 0
        attempts = 0
        consecutive_failures = 0
        max_consecutive_failures = 10  # Circuit breaker

        with open(output_path, "w", encoding="utf-8") as f:
            while generated < target_count and attempts < max_attempts:
                attempts += 1
                task_info = self.generate_task()
                trajectory = self.generate_trajectory(
                    task_info["task"], task_info["domain"]
                )
                if trajectory:
                    f.write(json.dumps(trajectory) + "\n")
                    generated += 1
                    consecutive_failures = 0
                    if generated % 10 == 0:
                        logger.info(f"Generated {generated}/{target_count} trajectories ({attempts} attempts)")
                else:
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        logger.error(
                            f"Circuit breaker: {max_consecutive_failures} consecutive failures. "
                            f"Stopping after {generated}/{target_count} trajectories."
                        )
                        break

        logger.info(
            f"Generated {generated} trajectories in {attempts} attempts → {output_path}"
        )
        return generated


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic GRPO training data")
    parser.add_argument("--target", type=int, default=552, help="Target trajectory count")
    parser.add_argument("--output", "-o", help="Output JSONL path")
    parser.add_argument("--output-dir", default="training_data", help="Output directory")
    parser.add_argument("--host", default=OLLAMA_HOST, help="Ollama host URL")
    parser.add_argument("--model", default=ARCHITECT_MODEL, help="Solver model name")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")

    gen = SyntheticTrajectoryGenerator(
        solver_host=args.host,
        solver_model=args.model,
        output_dir=args.output_dir,
    )
    count = gen.generate_dataset(target_count=args.target, output_path=args.output)
    print(f"Generated {count} trajectories")


if __name__ == "__main__":
    main()
