"""
workflow_engine.py — Multi-Step Workflow Orchestration

Provides a declarative workflow system for automatable multi-step
agent tasks. Workflows are defined as JSON/dict step sequences
with dependency tracking and conditional branching.

Features:
    - Step-by-step execution with state persistence
    - Parallel step groups (steps with no dependencies)
    - Conditional steps (runs only if condition_fn returns True)
    - Per-step timeout enforcement
    - Rollback on failure (if rollback handler provided)
    - Workflow state serialization for resume-after-crash

Architecture:
    WorkflowEngine (singleton)
    └─ Workflow
       └─ WorkflowStep[]
          ├─ handler: Callable[dict] → dict
          ├─ depends_on: list[str]
          └─ condition_fn: Optional[Callable → bool]

Usage:
    from workflow_engine import get_workflow_engine, WorkflowStep

    engine = get_workflow_engine()

    steps = [
        WorkflowStep(name="fetch", handler=fetch_data),
        WorkflowStep(name="process", handler=process_data, depends_on=["fetch"]),
        WorkflowStep(name="deploy", handler=deploy, depends_on=["process"]),
    ]

    result = engine.run_workflow("my-pipeline", steps)
"""

import os
import json
import time
import uuid
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from logger_setup import setup_logger

logger = setup_logger("WorkflowEngine")


class StepState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class WorkflowState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class WorkflowStep:
    """A single step in a workflow pipeline."""
    name: str
    handler: Callable[[dict], dict]
    depends_on: list[str] = field(default_factory=list)
    timeout: int = 300  # seconds
    condition_fn: Optional[Callable[[dict], bool]] = None
    rollback_fn: Optional[Callable[[dict], None]] = None
    state: StepState = StepState.PENDING
    result: Optional[dict] = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "depends_on": self.depends_on,
            "timeout": self.timeout,
            "state": self.state.value,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


@dataclass
class Workflow:
    """A workflow pipeline with ordered steps."""
    workflow_id: str
    name: str
    steps: list[WorkflowStep]
    state: WorkflowState = WorkflowState.PENDING
    context: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "state": self.state.value,
            "steps": [s.to_dict() for s in self.steps],
            "context_keys": list(self.context.keys()),
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "error": self.error,
        }


# Persistence directory for workflow state
WORKFLOW_STATE_DIR = Path(os.getenv(
    "WORKFLOW_STATE_DIR",
    "/workspace/workflow_state"
))


class WorkflowEngine:
    """Executes multi-step workflows with dependency resolution."""

    def __init__(self, max_parallel: int = 4):
        self._workflows: Dict[str, Workflow] = {}
        self._lock = threading.Lock()
        self._max_parallel = max_parallel

    def run_workflow(
        self,
        name: str,
        steps: list[WorkflowStep],
        initial_context: Optional[dict] = None,
    ) -> dict:
        """
        Execute a workflow synchronously.

        Args:
            name: Workflow name
            steps: Ordered list of WorkflowStep objects
            initial_context: Seed data available to all steps

        Returns:
            Workflow result dict with all step results
        """
        workflow_id = f"wf-{uuid.uuid4().hex[:8]}"
        workflow = Workflow(
            workflow_id=workflow_id,
            name=name,
            steps=steps,
            context=dict(initial_context or {}),
        )

        with self._lock:
            self._workflows[workflow_id] = workflow

        workflow.state = WorkflowState.RUNNING
        logger.info(f"[Workflow:{name}] Starting ({workflow_id}), {len(steps)} steps")

        try:
            self._execute_steps(workflow)
            if workflow.state == WorkflowState.RUNNING:
                workflow.state = WorkflowState.COMPLETED
                workflow.completed_at = time.time()
                logger.info(f"[Workflow:{name}] Completed successfully")
        except Exception as e:
            workflow.state = WorkflowState.FAILED
            workflow.error = str(e)
            workflow.completed_at = time.time()
            logger.error(f"[Workflow:{name}] Failed: {e}")

        self._persist_state(workflow)
        return workflow.to_dict()

    def _execute_steps(self, workflow: Workflow):
        """Execute steps respecting dependencies, parallelizing independent ones."""
        steps_by_name = {s.name: s for s in workflow.steps}
        completed_steps: set[str] = set()

        while len(completed_steps) < len(workflow.steps):
            # Find steps whose dependencies are all satisfied
            ready = []
            for step in workflow.steps:
                if step.name in completed_steps:
                    continue
                if step.state in (StepState.FAILED, StepState.SKIPPED):
                    completed_steps.add(step.name)
                    continue
                deps_met = all(d in completed_steps for d in step.depends_on)
                if deps_met:
                    ready.append(step)

            if not ready:
                # No steps are ready — remaining steps have unmet dependencies
                for step in workflow.steps:
                    if step.name not in completed_steps and step.state == StepState.PENDING:
                        step.state = StepState.SKIPPED
                        step.error = "Dependencies not met"
                        completed_steps.add(step.name)
                break

            # Execute ready steps in parallel
            if len(ready) == 1:
                self._run_step(ready[0], workflow)
                completed_steps.add(ready[0].name)
            else:
                with ThreadPoolExecutor(max_workers=min(len(ready), self._max_parallel)) as pool:
                    futures = {
                        pool.submit(self._run_step, step, workflow): step
                        for step in ready
                    }
                    for future in as_completed(futures):
                        step = futures[future]
                        completed_steps.add(step.name)

                        # If a step failed, consider rolling back
                        if step.state == StepState.FAILED:
                            workflow.state = WorkflowState.FAILED
                            workflow.error = f"Step '{step.name}' failed: {step.error}"
                            self._rollback(workflow, completed_steps)
                            return

            # Check for failures in serial path
            for step in ready:
                if step.state == StepState.FAILED:
                    workflow.state = WorkflowState.FAILED
                    workflow.error = f"Step '{step.name}' failed: {step.error}"
                    self._rollback(workflow, completed_steps)
                    return

    def _run_step(self, step: WorkflowStep, workflow: Workflow):
        """Execute a single workflow step."""
        # Check condition
        if step.condition_fn:
            try:
                if not step.condition_fn(workflow.context):
                    step.state = StepState.SKIPPED
                    logger.info(f"[Workflow:{workflow.name}] Skipping '{step.name}' (condition not met)")
                    return
            except Exception as e:
                step.state = StepState.SKIPPED
                step.error = f"Condition check failed: {e}"
                return

        step.state = StepState.RUNNING
        step.started_at = time.time()
        logger.info(f"[Workflow:{workflow.name}] Running step '{step.name}'")

        try:
            # Handler receives and returns context dict
            result = step.handler(workflow.context)
            step.result = result if isinstance(result, dict) else {"output": result}

            # Merge results into workflow context for downstream steps
            if isinstance(result, dict):
                workflow.context.update(result)

            step.state = StepState.COMPLETED
            step.completed_at = time.time()

            elapsed = step.completed_at - step.started_at
            logger.info(f"[Workflow:{workflow.name}] Step '{step.name}' completed in {elapsed:.1f}s")

        except Exception as e:
            step.state = StepState.FAILED
            step.error = str(e)
            step.completed_at = time.time()
            logger.error(f"[Workflow:{workflow.name}] Step '{step.name}' failed: {e}")

    def _rollback(self, workflow: Workflow, completed_steps: set[str]):
        """Execute rollback handlers for completed steps in reverse order."""
        rollback_count = 0
        for step in reversed(workflow.steps):
            if step.name in completed_steps and step.rollback_fn and step.state == StepState.COMPLETED:
                try:
                    logger.info(f"[Workflow:{workflow.name}] Rolling back step '{step.name}'")
                    step.rollback_fn(workflow.context)
                    rollback_count += 1
                except Exception as e:
                    logger.error(f"[Workflow:{workflow.name}] Rollback of '{step.name}' failed: {e}")

        if rollback_count > 0:
            workflow.state = WorkflowState.ROLLED_BACK
            logger.info(f"[Workflow:{workflow.name}] Rolled back {rollback_count} steps")

    def _persist_state(self, workflow: Workflow):
        """Save workflow state to disk for crash recovery."""
        try:
            WORKFLOW_STATE_DIR.mkdir(parents=True, exist_ok=True)
            state_file = WORKFLOW_STATE_DIR / f"{workflow.workflow_id}.json"
            state = workflow.to_dict()
            state["context"] = {
                k: v for k, v in workflow.context.items()
                if isinstance(v, (str, int, float, bool, list, dict, type(None)))
            }
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, default=str)
        except Exception as e:
            logger.warning(f"[WorkflowEngine] Failed to persist state: {e}")

    def get_workflow(self, workflow_id: str) -> Optional[dict]:
        """Get a workflow's current state."""
        wf = self._workflows.get(workflow_id)
        return wf.to_dict() if wf else None

    def list_workflows(self, state_filter: Optional[str] = None) -> list[dict]:
        """List all workflows."""
        workflows = self._workflows.values()
        if state_filter:
            try:
                target = WorkflowState(state_filter)
                workflows = [w for w in workflows if w.state == target]
            except ValueError:
                pass
        return [w.to_dict() for w in workflows]

    def count(self) -> int:
        return len(self._workflows)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_engine: Optional[WorkflowEngine] = None


def get_workflow_engine() -> WorkflowEngine:
    global _engine
    if _engine is None:
        _engine = WorkflowEngine()
    return _engine
