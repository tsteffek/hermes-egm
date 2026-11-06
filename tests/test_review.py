"""Behavior tests for bounded, snapshot-only Goldfish review."""

import importlib
import importlib.util
import unittest


class SnapshotTests(unittest.TestCase):
    def test_request_has_a_stable_snapshot_of_only_explicit_documents(self) -> None:
        self.assertIsNotNone(importlib.util.find_spec("hermes_egm"), "review package is missing")
        core = importlib.import_module("hermes_egm.review")
        request = core.ReviewRequest.parse(
            {
                "target": "design.md",
                "documents": [{"id": "design.md", "text": "# Design\nDeliver an event."}],
            }
        )
        self.assertEqual(request.target, "design.md")
        self.assertEqual(request.lenses, ("comprehension", "design", "readiness"))
        self.assertEqual(len(request.snapshot_id), 64)
        self.assertEqual(
            request.snapshot_id,
            core.ReviewRequest.parse(
                {
                    "documents": [{"text": "# Design\nDeliver an event.", "id": "design.md"}],
                    "target": "design.md",
                }
            ).snapshot_id,
        )
        self.assertIn("Deliver an event.", request.payload())
        self.assertNotIn("AGENTS.md", request.payload())


if __name__ == "__main__":
    unittest.main()
