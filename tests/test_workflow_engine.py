"""
Tests for the Workflow Engine (Phase 5).
"""

import os
import sys
import time
import unittest
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))


class TestStepState(unittest.TestCase):
    def test_states(self):
        from workflow_engine import StepState
        self.assertEqual(StepState.PENDING.value, "pending")
        self.assertEqual(StepState.COMPLETED.value, "completed")
        self.assertEqual(StepState.FAILED.value, "failed")
        self.assertEqual(StepState.SKIPPED.value, "skipped")


class TestWorkflowState(unittest.TestCase):
    def test_states(self):
        from workflow_engine import WorkflowState
        self.assertEqual(WorkflowState.COMPLETED.value, "completed")
        self.assertEqual(WorkflowState.ROLLED_BACK.value, "rolled_back")


class TestWorkflowStep(unittest.TestCase):
    def test_to_dict(self):
        from workflow_engine import WorkflowStep
        step = WorkflowStep(name="build", handler=lambda ctx: {"output": "ok"})
        d = step.to_dict()
        self.assertEqual(d["name"], "build")
        self.assertEqual(d["state"], "pending")
        self.assertIn("timeout", d)

    def test_defaults(self):
        from workflow_engine import WorkflowStep
        step = WorkflowStep(name="s", handler=lambda ctx: {})
        self.assertEqual(step.depends_on, [])
        self.assertEqual(step.timeout, 300)
        self.assertIsNone(step.condition_fn)


class TestWorkflow(unittest.TestCase):
    def test_to_dict(self):
        from workflow_engine import Workflow, WorkflowStep
        wf = Workflow(
            workflow_id="wf-test",
            name="test",
            steps=[WorkflowStep(name="a", handler=lambda ctx: {})],
        )
        d = wf.to_dict()
        self.assertEqual(d["name"], "test")
        self.assertEqual(len(d["steps"]), 1)


class TestWorkflowEngine(unittest.TestCase):
    def _get_engine(self):
        from workflow_engine import WorkflowEngine
        return WorkflowEngine()

    def test_simple_workflow(self):
        from workflow_engine import WorkflowStep
        engine = self._get_engine()

        def step_a(ctx):
            return {"a_done": True}
        def step_b(ctx):
            return {"b_done": ctx.get("a_done", False)}

        steps = [
            WorkflowStep(name="a", handler=step_a),
            WorkflowStep(name="b", handler=step_b, depends_on=["a"]),
        ]
        result = engine.run_workflow("simple", steps)
        self.assertEqual(result["state"], "completed")
        self.assertEqual(len(result["steps"]), 2)
        self.assertEqual(result["steps"][0]["state"], "completed")
        self.assertEqual(result["steps"][1]["state"], "completed")

    def test_parallel_steps(self):
        from workflow_engine import WorkflowStep
        engine = self._get_engine()
        order = []

        def step_a(ctx):
            order.append("a")
            return {}
        def step_b(ctx):
            order.append("b")
            return {}
        def step_c(ctx):
            order.append("c")
            return {}

        steps = [
            WorkflowStep(name="a", handler=step_a),
            WorkflowStep(name="b", handler=step_b),
            WorkflowStep(name="c", handler=step_c, depends_on=["a", "b"]),
        ]
        result = engine.run_workflow("parallel", steps)
        self.assertEqual(result["state"], "completed")
        # a and b should both complete before c
        self.assertIn("c", order)
        c_idx = order.index("c")
        self.assertIn("a", order[:c_idx + 1])
        self.assertIn("b", order[:c_idx + 1])

    def test_step_failure(self):
        from workflow_engine import WorkflowStep
        engine = self._get_engine()

        def fail_step(ctx):
            raise RuntimeError("intentional failure")

        steps = [
            WorkflowStep(name="fail", handler=fail_step),
        ]
        result = engine.run_workflow("failing", steps)
        self.assertEqual(result["state"], "failed")
        self.assertIn("intentional failure", result["error"])

    def test_conditional_step_skipped(self):
        from workflow_engine import WorkflowStep
        engine = self._get_engine()

        def always_skip(ctx):
            return False

        def step_handler(ctx):
            return {"ran": True}

        steps = [
            WorkflowStep(name="cond", handler=step_handler, condition_fn=always_skip),
        ]
        result = engine.run_workflow("conditional", steps)
        self.assertEqual(result["state"], "completed")
        self.assertEqual(result["steps"][0]["state"], "skipped")

    def test_conditional_step_runs(self):
        from workflow_engine import WorkflowStep
        engine = self._get_engine()

        def always_run(ctx):
            return True

        steps = [
            WorkflowStep(name="cond", handler=lambda ctx: {"ok": True}, condition_fn=always_run),
        ]
        result = engine.run_workflow("conditional-run", steps)
        self.assertEqual(result["steps"][0]["state"], "completed")

    def test_rollback_on_failure(self):
        from workflow_engine import WorkflowStep
        engine = self._get_engine()
        rolled_back = []

        def step_a(ctx):
            return {"a": True}
        def step_b(ctx):
            raise RuntimeError("b fails")
        def rollback_a(ctx):
            rolled_back.append("a")

        steps = [
            WorkflowStep(name="a", handler=step_a, rollback_fn=rollback_a),
            WorkflowStep(name="b", handler=step_b, depends_on=["a"]),
        ]
        result = engine.run_workflow("rollback", steps)
        self.assertIn(result["state"], ("failed", "rolled_back"))
        self.assertIn("a", rolled_back)

    def test_context_propagation(self):
        from workflow_engine import WorkflowStep
        engine = self._get_engine()

        def produce(ctx):
            return {"shared_key": 42}
        def consume(ctx):
            val = ctx.get("shared_key")
            return {"consumed": val}

        steps = [
            WorkflowStep(name="produce", handler=produce),
            WorkflowStep(name="consume", handler=consume, depends_on=["produce"]),
        ]
        result = engine.run_workflow("context", steps, initial_context={"seed": True})
        self.assertEqual(result["state"], "completed")

    def test_initial_context(self):
        from workflow_engine import WorkflowStep
        engine = self._get_engine()

        def check_seed(ctx):
            assert ctx.get("seed") is True
            return {"checked": True}

        steps = [WorkflowStep(name="check", handler=check_seed)]
        result = engine.run_workflow("seeded", steps, initial_context={"seed": True})
        self.assertEqual(result["state"], "completed")

    def test_unmet_dependencies_skip(self):
        from workflow_engine import WorkflowStep
        engine = self._get_engine()

        def fail_step(ctx):
            raise RuntimeError("fail")

        steps = [
            WorkflowStep(name="a", handler=fail_step),
            WorkflowStep(name="b", handler=lambda ctx: {}, depends_on=["a"]),
        ]
        result = engine.run_workflow("deps", steps)
        self.assertEqual(result["state"], "failed")

    def test_get_workflow(self):
        from workflow_engine import WorkflowStep
        engine = self._get_engine()
        result = engine.run_workflow("tracked", [
            WorkflowStep(name="x", handler=lambda ctx: {}),
        ])
        wf = engine.get_workflow(result["workflow_id"])
        self.assertIsNotNone(wf)
        self.assertEqual(wf["name"], "tracked")

    def test_get_workflow_nonexistent(self):
        engine = self._get_engine()
        self.assertIsNone(engine.get_workflow("nonexistent"))

    def test_list_workflows(self):
        from workflow_engine import WorkflowStep
        engine = self._get_engine()
        engine.run_workflow("a", [WorkflowStep(name="s", handler=lambda ctx: {})])
        engine.run_workflow("b", [WorkflowStep(name="s", handler=lambda ctx: {})])
        wfs = engine.list_workflows()
        self.assertEqual(len(wfs), 2)

    def test_list_workflows_filter(self):
        from workflow_engine import WorkflowStep
        engine = self._get_engine()
        engine.run_workflow("ok", [WorkflowStep(name="s", handler=lambda ctx: {})])
        engine.run_workflow("fail", [WorkflowStep(name="s", handler=lambda ctx: (_ for _ in ()).throw(RuntimeError("x")))])
        completed = engine.list_workflows(state_filter="completed")
        failed = engine.list_workflows(state_filter="failed")
        self.assertEqual(len(completed), 1)
        self.assertEqual(len(failed), 1)

    def test_count(self):
        from workflow_engine import WorkflowStep
        engine = self._get_engine()
        self.assertEqual(engine.count(), 0)
        engine.run_workflow("x", [WorkflowStep(name="s", handler=lambda ctx: {})])
        self.assertEqual(engine.count(), 1)

    def test_empty_workflow(self):
        engine = self._get_engine()
        result = engine.run_workflow("empty", [])
        self.assertEqual(result["state"], "completed")


class TestWorkflowSingleton(unittest.TestCase):
    def test_singleton(self):
        from workflow_engine import get_workflow_engine
        a = get_workflow_engine()
        b = get_workflow_engine()
        self.assertIs(a, b)


if __name__ == "__main__":
    unittest.main()
