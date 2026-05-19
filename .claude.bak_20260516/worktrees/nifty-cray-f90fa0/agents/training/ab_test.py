"""
A/B Testing harness for model lifecycle management.

Compares fine-tuned candidate models against base models using
probabilistic traffic splitting. Auto-promotes winners when the
candidate is statistically significantly better.

Usage:
    from training.ab_test import ABTestManager
    mgr = ABTestManager()
    mgr.start_test("code_developer", "marsrl-solver:v20260321", "qwen2.5-coder:14b")
"""

import json
import logging
import os
import sys
import random
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import TEMPLATE_DB_URL

logger = logging.getLogger("ABTest")


class ABTestManager:
    """Manage A/B tests for model comparisons."""

    def __init__(self, db_url: str = TEMPLATE_DB_URL):
        self.db_url = db_url

    def _get_conn(self):
        import psycopg2
        return psycopg2.connect(self.db_url)

    def start_test(
        self,
        template_id: str,
        candidate_model: str,
        base_model: str,
        traffic_split: float = 0.2,
        min_invocations: int = 100,
    ) -> int:
        """
        Start a new A/B test.

        Args:
            template_id: Which expertise template this test is for
            candidate_model: The fine-tuned model to evaluate
            base_model: The current production model
            traffic_split: Fraction of traffic routed to candidate (0.0–1.0)
            min_invocations: Minimum samples before evaluation

        Returns:
            test_id
        """
        conn = self._get_conn()
        cur = conn.cursor()

        # Check for existing active test on this template
        cur.execute(
            "SELECT id FROM swarm.ab_tests WHERE template_id = %s AND status = 'active'",
            (template_id,),
        )
        if cur.fetchone():
            cur.close()
            conn.close()
            raise ValueError(f"Active A/B test already exists for template {template_id}")

        cur.execute(
            """
            INSERT INTO swarm.ab_tests
                (template_id, candidate_model, base_model, traffic_split, min_invocations)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (template_id, candidate_model, base_model, traffic_split, min_invocations),
        )
        test_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

        logger.info(
            f"Started A/B test {test_id}: {candidate_model} vs {base_model} "
            f"on {template_id} ({traffic_split*100:.0f}% candidate traffic)"
        )
        return test_id

    def route_model(self, template_id: str, default_model: str) -> str:
        """
        Decide which model to use for a given template.

        If an active A/B test exists, probabilistically route to candidate.
        Otherwise returns the default model.
        """
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, candidate_model, base_model, traffic_split
                FROM swarm.ab_tests
                WHERE template_id = %s AND status = 'active'
                LIMIT 1
                """,
                (template_id,),
            )
            row = cur.fetchone()
            cur.close()
            conn.close()

            if not row:
                return default_model

            test_id, candidate, base, split = row
            if random.random() < split:
                logger.debug(f"[AB {test_id}] Routing to candidate: {candidate}")
                return candidate
            else:
                logger.debug(f"[AB {test_id}] Routing to base: {base}")
                return base

        except Exception as e:
            logger.debug(f"A/B routing failed (using default): {e}")
            return default_model

    def record_result(
        self,
        template_id: str,
        model_used: str,
        score: float,
        latency_ms: Optional[int] = None,
    ):
        """Record a single invocation result for an active A/B test."""
        try:
            conn = self._get_conn()
            cur = conn.cursor()

            # Find active test for this template
            cur.execute(
                "SELECT id FROM swarm.ab_tests WHERE template_id = %s AND status = 'active'",
                (template_id,),
            )
            row = cur.fetchone()
            if not row:
                cur.close()
                conn.close()
                return

            test_id = row[0]
            cur.execute(
                """
                INSERT INTO swarm.ab_test_results (test_id, model_used, score, latency_ms)
                VALUES (%s, %s, %s, %s)
                """,
                (test_id, model_used, score, latency_ms),
            )
            conn.commit()
            cur.close()
            conn.close()

            # Update Prometheus gauge
            try:
                from metrics import AB_TEST_SCORE
                arm = "candidate" if model_used != self._get_base_model(test_id) else "base"
                AB_TEST_SCORE.labels(test_id=str(test_id), arm=arm).set(score)
            except Exception:
                pass

        except Exception as e:
            logger.debug(f"Failed to record A/B result: {e}")

    def _get_base_model(self, test_id: int) -> Optional[str]:
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("SELECT base_model FROM swarm.ab_tests WHERE id = %s", (test_id,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            return row[0] if row else None
        except Exception:
            return None

    def evaluate_test(self, test_id: int) -> Dict[str, Any]:
        """
        Evaluate an A/B test and determine if there's a winner.

        Uses a simple t-test to check if the candidate is significantly
        better than the base (p < 0.05, improvement > 5%).

        Returns dict with: ready, winner, candidate_avg, base_avg, p_value, n_candidate, n_base
        """
        conn = self._get_conn()
        cur = conn.cursor()

        # Get test details
        cur.execute(
            "SELECT candidate_model, base_model, min_invocations FROM swarm.ab_tests WHERE id = %s",
            (test_id,),
        )
        test = cur.fetchone()
        if not test:
            cur.close()
            conn.close()
            return {"ready": False, "reason": "Test not found"}

        candidate_model, base_model, min_invocations = test

        # Get scores for each arm
        cur.execute(
            "SELECT score FROM swarm.ab_test_results WHERE test_id = %s AND model_used = %s",
            (test_id, candidate_model),
        )
        candidate_scores = [r[0] for r in cur.fetchall()]

        cur.execute(
            "SELECT score FROM swarm.ab_test_results WHERE test_id = %s AND model_used = %s",
            (test_id, base_model),
        )
        base_scores = [r[0] for r in cur.fetchall()]

        cur.close()
        conn.close()

        n_candidate = len(candidate_scores)
        n_base = len(base_scores)

        # Need enough samples from both arms
        if n_candidate < min_invocations // 5 or n_base < min_invocations // 2:
            return {
                "ready": False,
                "reason": f"Insufficient samples (candidate: {n_candidate}, base: {n_base})",
                "n_candidate": n_candidate,
                "n_base": n_base,
            }

        candidate_avg = sum(candidate_scores) / n_candidate if n_candidate else 0
        base_avg = sum(base_scores) / n_base if n_base else 0

        # Statistical test
        p_value = self._welch_t_test(candidate_scores, base_scores)
        improvement = (candidate_avg - base_avg) / base_avg if base_avg > 0 else 0

        winner = None
        if p_value < 0.05 and improvement > 0.05:
            winner = "candidate"
        elif p_value < 0.05 and improvement < -0.05:
            winner = "base"

        return {
            "ready": True,
            "winner": winner,
            "candidate_model": candidate_model,
            "base_model": base_model,
            "candidate_avg": candidate_avg,
            "base_avg": base_avg,
            "improvement": improvement,
            "p_value": p_value,
            "n_candidate": n_candidate,
            "n_base": n_base,
        }

    def _welch_t_test(self, a: List[float], b: List[float]) -> float:
        """Welch's t-test for unequal variances. Returns p-value."""
        import math

        n_a, n_b = len(a), len(b)
        if n_a < 2 or n_b < 2:
            return 1.0

        mean_a = sum(a) / n_a
        mean_b = sum(b) / n_b
        var_a = sum((x - mean_a) ** 2 for x in a) / (n_a - 1)
        var_b = sum((x - mean_b) ** 2 for x in b) / (n_b - 1)

        se = math.sqrt(var_a / n_a + var_b / n_b)
        if se == 0:
            return 1.0

        t_stat = (mean_a - mean_b) / se

        # Welch-Satterthwaite degrees of freedom
        num = (var_a / n_a + var_b / n_b) ** 2
        denom = (var_a / n_a) ** 2 / (n_a - 1) + (var_b / n_b) ** 2 / (n_b - 1)
        df = num / denom if denom > 0 else 1

        # Approximate p-value using normal distribution for large df
        # (avoids scipy dependency)
        p_value = 2 * (1 - self._normal_cdf(abs(t_stat)))
        return p_value

    @staticmethod
    def _normal_cdf(x: float) -> float:
        """Approximate standard normal CDF (Abramowitz & Stegun)."""
        import math
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    def conclude_test(self, test_id: int, winner: str):
        """
        Conclude an A/B test and record the winner.

        Args:
            test_id: The test to conclude
            winner: "candidate" or "base"
        """
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE swarm.ab_tests
            SET status = 'concluded', winner = %s, concluded_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (winner, test_id),
        )
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"A/B test {test_id} concluded: winner = {winner}")

    def promote_candidate(self, test_id: int):
        """
        Promote the candidate model to production for its template.

        Updates the expertise_template's default_model and bumps version.
        Also updates model_versions status.
        """
        conn = self._get_conn()
        cur = conn.cursor()

        # Get test details
        cur.execute(
            "SELECT template_id, candidate_model FROM swarm.ab_tests WHERE id = %s",
            (test_id,),
        )
        row = cur.fetchone()
        if not row:
            cur.close()
            conn.close()
            return

        template_id, candidate_model = row

        # Update template's default model
        cur.execute(
            """
            UPDATE swarm.expertise_templates
            SET default_model = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (candidate_model, template_id),
        )

        # Mark candidate model version as promoted
        cur.execute(
            """
            UPDATE swarm.model_versions
            SET status = 'promoted', promoted_at = CURRENT_TIMESTAMP
            WHERE ollama_model_name = %s AND status IN ('candidate', 'ab_testing')
            """,
            (candidate_model,),
        )

        # Retire any previously promoted versions for same base
        cur.execute(
            """
            UPDATE swarm.model_versions
            SET status = 'retired'
            WHERE ollama_model_name != %s
              AND status = 'promoted'
              AND base_model = (
                SELECT base_model FROM swarm.model_versions
                WHERE ollama_model_name = %s LIMIT 1
              )
            """,
            (candidate_model, candidate_model),
        )

        conn.commit()
        cur.close()
        conn.close()

        logger.info(f"Promoted {candidate_model} as default for {template_id}")

        # Update Prometheus
        try:
            from metrics import MODEL_VERSION_ACTIVE
            MODEL_VERSION_ACTIVE.labels(
                template_id=template_id,
                model_name=candidate_model,
                version_tag="promoted",
            ).set(1)
        except Exception:
            pass

    def get_active_tests(self) -> List[Dict[str, Any]]:
        """List all active A/B tests."""
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, template_id, candidate_model, base_model,
                       traffic_split, min_invocations, started_at
                FROM swarm.ab_tests WHERE status = 'active'
                ORDER BY started_at DESC
                """
            )
            tests = []
            for row in cur.fetchall():
                tests.append({
                    "id": row[0],
                    "template_id": row[1],
                    "candidate_model": row[2],
                    "base_model": row[3],
                    "traffic_split": row[4],
                    "min_invocations": row[5],
                    "started_at": row[6].isoformat() if row[6] else None,
                })
            cur.close()
            conn.close()
            return tests
        except Exception as e:
            logger.debug(f"Failed to list active tests: {e}")
            return []


# Singleton
_ab_manager: Optional[ABTestManager] = None

def get_ab_manager() -> ABTestManager:
    global _ab_manager
    if _ab_manager is None:
        _ab_manager = ABTestManager()
    return _ab_manager
