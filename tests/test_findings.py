"""Evidence is checked against literal supplied lines, not reviewer confidence."""

import unittest
from copy import deepcopy

from hermes_egm.review import InvalidReview, ReviewRequest, validate_findings


def finding():
    return {
        "severity": "major",
        "title": "No delivery timeout",
        "detail": "A stalled receiver could hold the worker indefinitely.",
        "suggestion": "Specify a bounded delivery timeout and test it.",
        "evidence": [{"document": "spec", "line": 2, "quote": "Deliver webhooks."}],
    }


def request():
    return ReviewRequest.parse(
        {
            "target": "spec",
            "documents": [{"id": "spec", "text": "# Design\nDeliver webhooks."}],
        }
    )


class FindingTests(unittest.TestCase):
    def test_accepts_a_grounded_finding_without_mutating_the_model_response(self) -> None:
        raw = {"findings": [finding()]}
        before = deepcopy(raw)
        accepted = validate_findings(raw, request(), "design")
        self.assertEqual(accepted[0]["lenses"], ["design"])
        self.assertEqual(accepted[0]["evidence"][0]["quote"], "Deliver webhooks.")
        self.assertEqual(raw, before)

    def test_invalid_findings_fail_closed_without_optional_jsonschema(self) -> None:
        raw = finding()
        variants = [
            {**raw, "severity": "approved"},
            {**raw, "title": " "},
            {**raw, "title": "x" * 161},
            {**raw, "detail": 42},
            {**raw, "extra": "run a command"},
            {**raw, "evidence": []},
            {**raw, "evidence": [{"document": "not-supplied", "line": 1, "quote": "x"}]},
            {**raw, "evidence": [{"document": "spec", "line": 99, "quote": "x"}]},
            {**raw, "evidence": [{"document": "spec", "line": True, "quote": "# Design"}]},
            {**raw, "evidence": [{"document": "spec", "line": 1, "quote": "Deliver webhooks."}]},
            {**raw, "evidence": [{"document": "spec", "line": 2, "quote": "Invented quote"}]},
            {**raw, "evidence": [{"document": "spec", "line": 2, "quote": " "}]},
        ]
        cases = [None, {}, [], {"findings": [], "approved": True}, {"findings": [raw] * 9}]
        cases += [{"findings": [value]} for value in variants]
        for value in cases:
            with self.subTest(value=str(value)[:100]), self.assertRaises(InvalidReview):
                validate_findings(value, request(), "design")
