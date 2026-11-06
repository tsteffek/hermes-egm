"""Input contracts fail before model usage or implicit context access."""

import unittest
from copy import deepcopy

from hermes_egm.review import InvalidReview, ReviewRequest


class InputTests(unittest.TestCase):
    def test_rejects_ambiguous_oversized_and_unexpected_inputs(self) -> None:
        good = {"target": "design.md", "documents": [{"id": "design.md", "text": "A design."}]}
        cases = [
            {},
            [],
            {**good, "parent_chat": "must never be forwarded"},
            {**good, "target": "missing"},
            {**good, "target": ""},
            {**good, "documents": []},
            {**good, "documents": good["documents"] * 2},
            {**good, "documents": [{"id": "design.md", "text": " "}]},
            {**good, "documents": [{"id": "bad\nlabel", "text": "data"}]},
            {**good, "documents": [{"id": "design.md", "text": "x" * 48001}]},
            {**good, "documents": [{"id": "design.md", "text": "a", "secret": "extra"}]},
            {**good, "documents": [{"id": str(i), "text": "a"} for i in range(9)]},
            {**good, "documents": [{"id": "design.md", "text": "\ud800"}]},
            {**good, "lenses": []},
            {**good, "lenses": ["design", "design"]},
            {**good, "lenses": ["invented"]},
            {**good, "lenses": "design"},
        ]
        for case in cases:
            with self.subTest(case=str(case)[:100]), self.assertRaises(InvalidReview):
                ReviewRequest.parse(case)

    def test_snapshot_is_immutable_and_fingerprint_changes_with_content(self) -> None:
        original = {"target": "a", "documents": [{"id": "a", "text": "one"}]}
        changed = deepcopy(original)
        changed["documents"][0]["text"] = "two"
        first = ReviewRequest.parse(original)
        self.assertNotEqual(first.snapshot_id, ReviewRequest.parse(changed).snapshot_id)
        original["documents"][0]["text"] = "three"
        self.assertEqual(first.documents[0].text, "one")
