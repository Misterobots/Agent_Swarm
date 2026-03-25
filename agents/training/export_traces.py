"""
Export high-reward Langfuse traces to GRPO-compatible JSONL.

Queries traces tagged with training_candidate score > 0.8,
fetches full trace + observations, and converts to multi-turn
conversation format suitable for GRPO training.

Usage:
    python -m training.export_traces --output training_data/exported.jsonl
"""

import json
import os
import sys
import logging
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any

import requests

# Add parent to path for config imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import LANGFUSE_HOST
from training.reward_function import MarsRewardFunction

logger = logging.getLogger("TraceExporter")

LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "pk-lf-dev")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "sk-lf-dev")


class TraceExporter:
    """Export Langfuse training_candidate traces to GRPO JSONL."""

    def __init__(
        self,
        langfuse_host: str = LANGFUSE_HOST,
        public_key: str = LANGFUSE_PUBLIC_KEY,
        secret_key: str = LANGFUSE_SECRET_KEY,
        output_dir: str = "training_data",
    ):
        self.host = langfuse_host.rstrip("/")
        self.auth = (public_key, secret_key)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.reward_fn = MarsRewardFunction()
        self._exported_ids = self._load_exported_ids()

    def _api_get(self, path: str, params: Optional[dict] = None) -> dict:
        """GET request to Langfuse public API."""
        url = f"{self.host}/api/public{path}"
        resp = requests.get(url, auth=self.auth, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _load_exported_ids(self) -> set:
        """Load previously exported trace IDs for deduplication."""
        ids_file = self.output_dir / "exported_ids.json"
        if ids_file.exists():
            return set(json.loads(ids_file.read_text()))
        return set()

    def _save_exported_ids(self):
        """Persist exported trace IDs."""
        ids_file = self.output_dir / "exported_ids.json"
        ids_file.write_text(json.dumps(sorted(self._exported_ids)))

    def fetch_training_candidates(
        self, since_hours: int = 168, limit: int = 500
    ) -> List[dict]:
        """
        Fetch traces that have a training_candidate score.
        Returns list of trace detail dicts with their observations.
        """
        # Step 1: Get scores named "training_candidate"
        try:
            scores_resp = self._api_get("/scores", params={
                "name": "training_candidate",
                "limit": limit,
            })
        except Exception as e:
            logger.error(f"Failed to fetch training candidate scores: {e}")
            return []

        scores = scores_resp.get("data", [])
        logger.info(f"Found {len(scores)} training_candidate scores")

        candidates = []
        for score in scores:
            trace_id = score.get("traceId")
            if not trace_id or trace_id in self._exported_ids:
                continue

            try:
                # Step 2: Fetch full trace
                trace = self._api_get(f"/traces/{trace_id}")

                # Step 3: Fetch observations for this trace
                obs_resp = self._api_get("/observations", params={
                    "traceId": trace_id,
                    "limit": 100,
                })
                observations = obs_resp.get("data", [])

                candidates.append({
                    "trace": trace,
                    "observations": observations,
                    "score_value": score.get("value", 1.0),
                })
            except Exception as e:
                logger.warning(f"Failed to fetch trace {trace_id}: {e}")
                continue

        logger.info(f"Fetched {len(candidates)} new candidate traces")
        return candidates

    def trace_to_grpo_trajectory(
        self, trace_detail: dict, observations: List[dict]
    ) -> Optional[dict]:
        """
        Convert a Langfuse trace + observations into GRPO trajectory format.

        Returns:
            {
                "id": trace_id,
                "conversations": [...],
                "reward": {"correctness": float, "efficiency": float, "safety": float},
                "metadata": {...}
            }
        """
        trace = trace_detail
        trace_id = trace.get("id", "unknown")
        metadata = trace.get("metadata", {})

        # Extract task input
        task_input = trace.get("input")
        if isinstance(task_input, dict):
            task_input = task_input.get("input", json.dumps(task_input))
        elif not isinstance(task_input, str):
            task_input = str(task_input) if task_input else None

        if not task_input:
            logger.debug(f"Skipping trace {trace_id}: no input")
            return None

        # Build conversation from observations
        conversations = [{"role": "user", "content": task_input}]

        # Sort observations by start time
        sorted_obs = sorted(
            observations,
            key=lambda o: o.get("startTime", ""),
        )

        for obs in sorted_obs:
            obs_type = obs.get("type", "")
            obs_name = obs.get("name", "")

            if obs_type == "GENERATION":
                # LLM generation — solver or corrector output
                output = obs.get("output")
                if isinstance(output, dict):
                    output = output.get("content", json.dumps(output))
                elif not isinstance(output, str):
                    output = str(output) if output else ""

                if output:
                    # Check for tool calls in the output
                    tool_calls = self._extract_tool_calls(output)
                    entry: Dict[str, Any] = {
                        "role": "assistant",
                        "content": output,
                    }
                    if tool_calls:
                        entry["tool_calls"] = tool_calls
                    conversations.append(entry)

            elif obs_type == "SPAN" and "tool" in obs_name.lower():
                # Tool execution result
                tool_output = obs.get("output")
                if isinstance(tool_output, dict):
                    tool_output = json.dumps(tool_output)
                elif not isinstance(tool_output, str):
                    tool_output = str(tool_output) if tool_output else ""

                if tool_output:
                    conversations.append({
                        "role": "tool",
                        "name": obs_name,
                        "content": tool_output,
                    })

        # Fallback: use trace-level output if no GENERATION observations were found
        # (covers non-MarsRL agents: IoT, Image, Conversation, Research, etc.)
        if len(conversations) < 2:
            trace_output = trace.get("output")
            if isinstance(trace_output, dict):
                trace_output = trace_output.get("response", trace_output.get("content", ""))
            if isinstance(trace_output, str) and trace_output.strip():
                conversations.append({"role": "assistant", "content": trace_output})

        # Need at least user + one assistant turn
        if len(conversations) < 2:
            logger.debug(f"Skipping trace {trace_id}: insufficient conversation turns")
            return None

        # Extract scores for reward computation
        final_score = 0.0
        iterations = 1
        safety_passed = True

        # Try to get scores from trace metadata or observations
        for obs in sorted_obs:
            obs_name = obs.get("name", "")
            if "verifier" in obs_name.lower() and obs.get("output"):
                try:
                    v_out = obs["output"]
                    if isinstance(v_out, dict):
                        final_score = max(final_score, v_out.get("score", 0.0))
                except (TypeError, ValueError):
                    pass

        # Count iterations from generation observations
        gen_count = sum(1 for o in sorted_obs if o.get("type") == "GENERATION")
        iterations = max(1, gen_count)

        # Use the training_candidate score as a proxy for quality
        reward = self.reward_fn.compute_reward(
            final_score=max(final_score, 0.8),  # training candidates are > 0.8 by definition
            iterations=iterations,
            safety_passed=safety_passed,
        )

        return {
            "id": trace_id,
            "conversations": conversations,
            "reward": {
                "correctness": reward.correctness,
                "efficiency": reward.efficiency,
                "safety": reward.safety,
                "composite": reward.composite,
            },
            "metadata": {
                "template_id": metadata.get("template_id"),
                "template_version": metadata.get("template_version"),
                "intent": metadata.get("intent"),
                "session_id": trace.get("sessionId"),
                "exported_at": datetime.utcnow().isoformat(),
            },
        }

    def _extract_tool_calls(self, text: str) -> List[dict]:
        """Extract structured tool calls from assistant output text."""
        tool_calls = []
        # Look for JSON tool call patterns (as used by architect agent)
        try:
            # Try to find JSON blocks that look like tool calls
            import re
            pattern = r'\{\s*"name"\s*:\s*"(\w+)"\s*,\s*"arguments"\s*:'
            for match in re.finditer(pattern, text):
                start = match.start()
                # Find the matching closing brace
                depth = 0
                for i, c in enumerate(text[start:], start):
                    if c == "{":
                        depth += 1
                    elif c == "}":
                        depth -= 1
                        if depth == 0:
                            try:
                                tool_call = json.loads(text[start:i + 1])
                                tool_calls.append(tool_call)
                            except json.JSONDecodeError:
                                pass
                            break
        except Exception:
            pass
        return tool_calls

    def export_dataset(
        self,
        output_path: Optional[str] = None,
        min_score: float = 0.8,
        since_hours: int = 168,
        template_id: Optional[str] = None,
    ) -> int:
        """
        Main entry point: fetch training candidates, convert, write JSONL.

        Args:
            template_id: If provided, only export traces from this agent template
                         (e.g. 'code_developer', 'creative_writer').
        Returns count of exported trajectories.
        """
        if output_path is None:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            output_path = str(self.output_dir / f"grpo_traces_{timestamp}.jsonl")

        candidates = self.fetch_training_candidates(
            since_hours=since_hours,
        )

        exported = 0
        skipped_template = 0
        with open(output_path, "w", encoding="utf-8") as f:
            for candidate in candidates:
                trajectory = self.trace_to_grpo_trajectory(
                    candidate["trace"],
                    candidate["observations"],
                )
                if trajectory:
                    # Filter by template_id if specified
                    if template_id:
                        trace_template = trajectory.get("metadata", {}).get("template_id")
                        if trace_template != template_id:
                            skipped_template += 1
                            continue
                    f.write(json.dumps(trajectory) + "\n")
                    self._exported_ids.add(trajectory["id"])
                    exported += 1

        if template_id:
            logger.info(
                f"Template filter '{template_id}': exported {exported}, "
                f"skipped {skipped_template} from other templates"
            )

        self._save_exported_ids()
        logger.info(f"Exported {exported} trajectories to {output_path}")
        return exported


def main():
    parser = argparse.ArgumentParser(description="Export Langfuse traces to GRPO JSONL")
    parser.add_argument("--output", "-o", help="Output JSONL path")
    parser.add_argument("--output-dir", default="training_data", help="Output directory")
    parser.add_argument("--since-hours", type=int, default=168, help="Look back N hours")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")

    exporter = TraceExporter(output_dir=args.output_dir)
    count = exporter.export_dataset(
        output_path=args.output,
        since_hours=args.since_hours,
    )
    print(f"Exported {count} trajectories")


if __name__ == "__main__":
    main()
