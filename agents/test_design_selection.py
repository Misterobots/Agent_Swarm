import tempfile
import unittest
from unittest.mock import patch

from handlers.design import resolve_design_model
import brooks


class DesignAndWorkshopIsolationTests(unittest.TestCase):
    def test_design_keeps_explicit_selected_model(self):
        self.assertEqual(resolve_design_model({"model": "qwen3:14b"}, "qwen3-coder:30b"), "qwen3:14b")
        self.assertEqual(resolve_design_model({}, "qwen3-coder:30b"), "qwen3-coder:30b")

    def test_pending_workshops_are_scoped_to_their_session(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(brooks, "CONTEXT_DIR", directory):
            brooks.save_workshop_state("Answer any or all of these and I'll draft your Product Brief.", "Alpha", "owner", "alpha")
            self.assertIsNotNone(brooks.get_workshop_state("owner", "alpha"))
            self.assertIsNone(brooks.get_workshop_state("owner", "beta"))
            brooks.clear_workshop_state("owner", "alpha")
            self.assertIsNone(brooks.get_workshop_state("owner", "alpha"))
