"""
Async Template Updater
========================

Background task that monitors performance_history, updates template
version metrics, and optionally bumps versions when performance
improves significantly.

Runs as an asyncio task inside the agent runtime container.
"""

import asyncio
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Configurable via environment
UPDATE_INTERVAL_SECONDS = int(os.getenv("TEMPLATE_UPDATE_INTERVAL_SECONDS", "300"))  # 5 min
PRUNE_INTERVAL_SECONDS = int(os.getenv("TEMPLATE_PRUNE_INTERVAL_SECONDS", "86400"))  # 24 hours
PRUNE_RETENTION_DAYS = int(os.getenv("TEMPLATE_PRUNE_RETENTION_DAYS", "30"))
SCORE_IMPROVEMENT_THRESHOLD = float(os.getenv("TEMPLATE_SCORE_THRESHOLD", "0.05"))
MIN_INVOCATIONS_FOR_BUMP = int(os.getenv("TEMPLATE_MIN_INVOCATIONS", "50"))
HIGH_SCORE_THRESHOLD = float(os.getenv("TEMPLATE_HIGH_SCORE", "0.8"))
LOW_SCORE_WARNING = float(os.getenv("TEMPLATE_LOW_SCORE_WARNING", "0.5"))


class AsyncTemplateUpdater:
    """
    Background updater that periodically:
    1. Checks performance summaries for each template
    2. Updates version avg_score from recent invocations
    3. Warns if score drops below threshold
    4. Creates checkpoint version bumps for high-performing templates
    5. Prunes old performance records
    """

    def __init__(self, registry=None):
        self._registry = registry
        self._task: Optional[asyncio.Task] = None
        self._prune_task: Optional[asyncio.Task] = None
        self._running = False

    @property
    def registry(self):
        if self._registry is None:
            from expertise.template_registry import get_template_registry
            self._registry = get_template_registry()
        return self._registry

    async def start(self):
        """Start the background update loop."""
        if self._running:
            logger.warning("[TemplateUpdater] Already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._update_loop())
        self._prune_task = asyncio.create_task(self._prune_loop())
        logger.info(
            f"[TemplateUpdater] Started (update every {UPDATE_INTERVAL_SECONDS}s, "
            f"prune every {PRUNE_INTERVAL_SECONDS}s)"
        )

    async def stop(self):
        """Stop the background update loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._prune_task:
            self._prune_task.cancel()
            try:
                await self._prune_task
            except asyncio.CancelledError:
                pass
        logger.info("[TemplateUpdater] Stopped")

    async def _update_loop(self):
        """Main update loop — runs every UPDATE_INTERVAL_SECONDS."""
        while self._running:
            try:
                await asyncio.sleep(UPDATE_INTERVAL_SECONDS)
                await self._run_update_cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[TemplateUpdater] Update cycle error: {e}")
                await asyncio.sleep(60)  # Back off on error

    async def _prune_loop(self):
        """Prune loop — runs every PRUNE_INTERVAL_SECONDS."""
        while self._running:
            try:
                await asyncio.sleep(PRUNE_INTERVAL_SECONDS)
                count = self.registry.prune_old_records(days=PRUNE_RETENTION_DAYS)
                if count > 0:
                    logger.info(f"[TemplateUpdater] Pruned {count} records older than {PRUNE_RETENTION_DAYS} days")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[TemplateUpdater] Prune error: {e}")

    async def _run_update_cycle(self):
        """Single update cycle: check all templates."""
        templates = self.registry.list_templates()
        if not templates:
            return

        for template in templates:
            try:
                await self._process_template(template.id, template.current_version)
            except Exception as e:
                logger.error(f"[TemplateUpdater] Error processing {template.id}: {e}")

    async def _process_template(self, template_id: str, current_version: str):
        """Process a single template: update metrics, check for version bump, evaluate A/B tests."""
        summary = self.registry.get_performance_summary(template_id, window_hours=24)
        if not summary or summary.total_invocations == 0:
            return

        # Get current version's stored avg_score
        version = self.registry.get_template_version(template_id, current_version)
        if not version:
            return

        old_avg = version.avg_score
        new_avg = summary.avg_score
        total = summary.total_invocations

        # Log warning for degraded templates.
        # Only fire when avg_score > 0: a zero average means no invocations have
        # been explicitly scored yet (all final_scores were None), not that the
        # template is actually performing badly.
        if 0 < new_avg < LOW_SCORE_WARNING and total >= 10:
            logger.warning(
                f"[TemplateUpdater] DEGRADED: {template_id} v{current_version} "
                f"avg_score={new_avg:.3f} (threshold={LOW_SCORE_WARNING}) "
                f"over {total} invocations"
            )

        # Check if we should create a checkpoint version bump
        if (
            total >= MIN_INVOCATIONS_FOR_BUMP
            and new_avg >= HIGH_SCORE_THRESHOLD
            and new_avg - old_avg >= SCORE_IMPROVEMENT_THRESHOLD
        ):
            logger.info(
                f"[TemplateUpdater] Version bump triggered for {template_id}: "
                f"avg_score improved from {old_avg:.3f} to {new_avg:.3f} "
                f"over {total} invocations"
            )
            self.registry.bump_version(template_id)

        # --- A/B Test Auto-Evaluation ---
        await self._evaluate_ab_tests(template_id)

    async def _evaluate_ab_tests(self, template_id: str):
        """Check for concluded A/B tests and auto-promote winners."""
        try:
            from training.ab_test import get_ab_manager
        except ImportError:
            return

        try:
            ab_mgr = get_ab_manager()
            active_tests = ab_mgr.get_active_tests()

            for test in active_tests:
                if test["template_id"] != template_id:
                    continue

                test_id = test["id"]
                result = ab_mgr.evaluate_test(test_id)

                if not result.get("ready"):
                    logger.debug(
                        f"[TemplateUpdater] A/B test {test_id} not ready: "
                        f"{result.get('reason', 'insufficient data')}"
                    )
                    continue

                winner = result.get("winner")
                if winner == "candidate":
                    logger.info(
                        f"[TemplateUpdater] A/B test {test_id} WINNER: candidate "
                        f"({result['candidate_model']}) avg={result['candidate_avg']:.3f} "
                        f"vs base avg={result['base_avg']:.3f} "
                        f"(improvement={result['improvement']:.1%}, p={result['p_value']:.4f})"
                    )
                    ab_mgr.conclude_test(test_id, "candidate")
                    ab_mgr.promote_candidate(test_id)
                    self.registry.bump_version(template_id)

                elif winner == "base":
                    logger.info(
                        f"[TemplateUpdater] A/B test {test_id} WINNER: base "
                        f"({result['base_model']}) — candidate underperformed "
                        f"(improvement={result['improvement']:.1%}, p={result['p_value']:.4f})"
                    )
                    ab_mgr.conclude_test(test_id, "base")

                else:
                    logger.debug(
                        f"[TemplateUpdater] A/B test {test_id}: no significant difference yet "
                        f"(p={result['p_value']:.4f})"
                    )

        except Exception as e:
            logger.error(f"[TemplateUpdater] A/B test evaluation failed for {template_id}: {e}")
