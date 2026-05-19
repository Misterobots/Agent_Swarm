"""
Multi-objective reward function for GRPO training.

Aligned with MarsRL scoring:
  - Correctness (weight 0.5): verifier final_score
  - Efficiency (weight 0.3): 1.0 / iterations (fewer corrections = better)
  - Safety (weight 0.2): binary pass/fail from llama-guard
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class RewardSignal:
    """Composite reward for a single trajectory."""
    correctness: float  # 0.0–1.0 from verifier
    efficiency: float   # 1.0 / iterations
    safety: float       # 1.0 if passed, 0.0 if blocked
    composite: float    # weighted sum


class MarsRewardFunction:
    """Multi-objective reward aligned with MarsRL verifier scoring."""

    def __init__(
        self,
        correctness_weight: float = 0.5,
        efficiency_weight: float = 0.3,
        safety_weight: float = 0.2,
    ):
        self.w_correct = correctness_weight
        self.w_efficiency = efficiency_weight
        self.w_safety = safety_weight

    def compute_reward(
        self,
        final_score: float,
        iterations: int,
        safety_passed: bool,
    ) -> RewardSignal:
        """Compute composite reward for a single trajectory."""
        correctness = max(0.0, min(1.0, final_score))
        efficiency = 1.0 / max(1, iterations)
        safety = 1.0 if safety_passed else 0.0

        composite = (
            self.w_correct * correctness
            + self.w_efficiency * efficiency
            + self.w_safety * safety
        )

        return RewardSignal(
            correctness=correctness,
            efficiency=efficiency,
            safety=safety,
            composite=composite,
        )

    def compute_group_advantages(
        self, rewards: List[RewardSignal]
    ) -> List[float]:
        """
        GRPO: compute advantage relative to group mean.
        Each trajectory's advantage = its composite - mean(group composites).
        """
        if not rewards:
            return []
        mean_reward = sum(r.composite for r in rewards) / len(rewards)
        return [r.composite - mean_reward for r in rewards]

    def reward_from_trajectory(self, trajectory: dict) -> RewardSignal:
        """Extract reward from a GRPO trajectory dict."""
        reward_data = trajectory.get("reward", {})
        return RewardSignal(
            correctness=reward_data.get("correctness", 0.0),
            efficiency=reward_data.get("efficiency", 0.0),
            safety=reward_data.get("safety", 1.0),
            composite=(
                self.w_correct * reward_data.get("correctness", 0.0)
                + self.w_efficiency * reward_data.get("efficiency", 0.0)
                + self.w_safety * reward_data.get("safety", 1.0)
            ),
        )
