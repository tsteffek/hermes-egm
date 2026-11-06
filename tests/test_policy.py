"""Operator activation settings default to suggestion, never automatic spending."""

import dataclasses
import importlib
import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

from hermes_egm.policy import ActivationPolicy, InvalidPolicy


class ActivationPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_default_policy_is_suggest_with_no_automatic_project_scope(self) -> None:
        self.assertIsNotNone(
            importlib.util.find_spec("hermes_egm.policy"), "activation policy is not implemented"
        )
        policy = importlib.import_module("hermes_egm.policy").ActivationPolicy.parse({})
        self.assertEqual(policy.activation, "suggest")
        self.assertEqual(policy.auto_projects, ())
        self.assertEqual(policy.auto_max_reviews_per_session, 1)

    def test_unknown_settings_and_invalid_activation_are_rejected(self) -> None:
        for settings in (
            {"activation": "always"},
            {"activation": 1},
            {"activation": None},
            {"auto_project": []},
        ):
            with self.subTest(settings=settings), self.assertRaises(InvalidPolicy):
                ActivationPolicy.parse(settings)

    def test_session_limit_accepts_1_to_3_and_rejects_other_values(self) -> None:
        for value in (1, 2, 3):
            self.assertEqual(
                ActivationPolicy.parse(
                    {"auto_max_reviews_per_session": value}
                ).auto_max_reviews_per_session,
                value,
            )
        for value in (0, 4, -1, "2", 2.0, True, None):
            with self.subTest(value=value), self.assertRaises(InvalidPolicy):
                ActivationPolicy.parse({"auto_max_reviews_per_session": value})

    def test_auto_projects_requires_an_absolute_existing_directory_list(self) -> None:
        a_file = self.tmp / "file.txt"
        a_file.write_text("x")
        for entry in (
            "relative/path",
            str(self.tmp / "missing"),
            str(a_file),
            "/",
            42,
            None,
        ):
            with self.subTest(entry=entry), self.assertRaises(InvalidPolicy):
                ActivationPolicy.parse({"auto_projects": [entry]})
        with self.assertRaises(InvalidPolicy):
            ActivationPolicy.parse({"auto_projects": "not-a-list"})

    def test_projects_resolve_canonically_and_deduplicate(self) -> None:
        real = self.tmp / "real"
        real.mkdir()
        link = self.tmp / "link"
        link.symlink_to(real)
        dotted = self.tmp / "real" / ".." / "real"
        policy = ActivationPolicy.parse({"auto_projects": [str(link), str(dotted), str(real)]})
        self.assertEqual(policy.auto_projects, (real.resolve(),))

    def test_approved_root_matches_descendants_not_string_prefixes(self) -> None:
        root = self.tmp / "proj"
        (root / "src").mkdir(parents=True)
        sibling = self.tmp / "proj-other"
        sibling.mkdir()
        policy = ActivationPolicy.parse({"activation": "auto", "auto_projects": [str(root)]})
        self.assertEqual(policy.approved_root(str(root / "src")), root.resolve())
        self.assertEqual(policy.approved_root(root), root.resolve())
        self.assertIsNone(policy.approved_root(str(sibling)))
        self.assertIsNone(policy.approved_root(str(self.tmp)))
        self.assertIsNone(policy.approved_root(None))
        self.assertIsNone(policy.approved_root(123))
        self.assertIsNone(policy.approved_root(""))

    def test_approved_root_chooses_the_deepest_root_through_symlinks(self) -> None:
        outer = self.tmp / "outer"
        inner = outer / "inner"
        deep = inner / "deep"
        deep.mkdir(parents=True)
        link = self.tmp / "inner-link"
        link.symlink_to(inner)
        policy = ActivationPolicy.parse({"auto_projects": [str(outer), str(inner)]})
        self.assertEqual(policy.approved_root(str(deep)), inner.resolve())
        self.assertEqual(policy.approved_root(deep), inner.resolve())
        self.assertEqual(policy.approved_root(str(link)), inner.resolve())

    def test_workspace_identity_requires_an_existing_absolute_directory(self) -> None:
        import os

        policy = ActivationPolicy.parse({"auto_projects": [str(self.tmp)]})
        file = self.tmp / "not-a-directory"
        file.write_text("x")
        for cwd in (os.path.relpath(self.tmp), self.tmp / "missing", file):
            with self.subTest(cwd=cwd):
                self.assertIsNone(policy.approved_root(cwd))

    def test_no_configured_projects_never_approves_a_cwd(self) -> None:
        policy = ActivationPolicy.parse({"activation": "auto"})
        self.assertIsNone(policy.approved_root(str(self.tmp)))

    def test_policy_is_frozen(self) -> None:
        policy = ActivationPolicy.parse({})
        with self.assertRaises(dataclasses.FrozenInstanceError):
            policy.__setattr__("activation", "auto")
