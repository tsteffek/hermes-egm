"""The durable automatic-admission ledger is atomic, hash-only and restart-safe."""

import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path
from typing import Any

from hermes_egm import auto_store
from hermes_egm.auto_store import AutoReviewStore
from hermes_egm.policy import ActivationPolicy


class AutoReviewStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.db = Path(self._dir.name) / "automatic-reviews.sqlite3"
        self.store = self._connect_store()

    def _connect_store(self) -> AutoReviewStore:
        return AutoReviewStore(lambda: sqlite3.connect(self.db))

    def _root(self, name: str = "proj") -> Path:
        root = Path(self._dir.name) / name
        root.mkdir(exist_ok=True)
        return root.resolve()

    def _policy(
        self,
        *,
        activation: str = "auto",
        projects: tuple[Path, ...] = (),
        limit: int = 1,
    ) -> ActivationPolicy:
        return ActivationPolicy.parse(
            {
                "activation": activation,
                "auto_projects": [str(project) for project in projects],
                "auto_max_reviews_per_session": limit,
            }
        )

    def test_preserves_host_selected_sqlite_journal_mode(self) -> None:
        with closing(sqlite3.connect(self.db)) as connection:
            connection.execute("PRAGMA journal_mode=DELETE")
        self.store.enroll("s", self._root(), 1)
        with closing(sqlite3.connect(self.db)) as connection:
            self.assertEqual(connection.execute("PRAGMA journal_mode").fetchone()[0], "delete")

    def test_reserve_requires_auto_activation_and_a_known_session(self) -> None:
        root = self._root()
        auto = self._policy(projects=(root,))
        self.assertEqual(self.store.reserve("s", "snap", auto), "missing_session")
        self.assertEqual(self.store.reserve(None, "snap", auto), "missing_session")
        self.store.enroll("s", root, 1)
        for activation in ("manual", "suggest"):
            policy = self._policy(activation=activation, projects=(root,))
            self.assertEqual(self.store.reserve("s", "snap", policy), "automatic_disabled")
        self.assertEqual(self.store.reserve("other", "snap", auto), "missing_session")
        self.assertEqual(self.store.reserve("s", "snap", auto), "allowed")

    def test_unknown_session_and_forged_identifier_are_denied(self) -> None:
        root = self._root()
        policy = self._policy(projects=(root,))
        self.store.enroll("real-session", root, 1)
        for forged in ("", None, 7, b"real-session"):
            with self.subTest(forged=forged):
                self.assertEqual(self.store.reserve(forged, "snap", policy), "missing_session")
        self.assertEqual(self.store.reserve("real-session2", "snap", policy), "missing_session")

    def test_duplicate_snapshot_is_denied_and_precedes_the_limit(self) -> None:
        root = self._root()
        policy = self._policy(projects=(root,), limit=2)
        self.store.enroll("s", root, 2)
        self.assertEqual(self.store.reserve("s", "snap-a", policy), "allowed")
        self.assertEqual(self.store.reserve("s", "snap-a", policy), "duplicate_snapshot")
        self.assertEqual(self.store.reserve("s", "snap-b", policy), "allowed")
        self.assertEqual(self.store.reserve("s", "snap-c", policy), "automatic_limit_reached")
        self.assertEqual(self.store.reserve("s", "snap-a", policy), "duplicate_snapshot")

    def test_attempt_is_recorded_before_use_and_shared_across_connections(self) -> None:
        root = self._root()
        policy = self._policy(projects=(root,), limit=1)
        self.store.enroll("s", root, 1)
        other = self._connect_store()
        self.assertEqual(other.reserve("s", "snap-a", policy), "allowed")
        self.assertEqual(self.store.reserve("s", "snap-b", policy), "automatic_limit_reached")

    def test_concurrent_reservations_never_exceed_the_limit(self) -> None:
        root = self._root()
        policy = self._policy(projects=(root,), limit=1)
        self.store.enroll("s", root, 1)
        results: list[str] = []
        lock = threading.Lock()
        barrier = threading.Barrier(5)

        def worker(index: int) -> None:
            barrier.wait()
            outcome = self.store.reserve("s", f"snap-{index}", policy)
            with lock:
                results.append(outcome)

        threads = [threading.Thread(target=worker, args=(index,)) for index in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(results), 5)
        self.assertEqual(results.count("allowed"), 1)
        self.assertEqual(results.count("automatic_limit_reached"), 4)

    def test_attempts_and_dedup_survive_reopen(self) -> None:
        root = self._root()
        policy = self._policy(projects=(root,), limit=2)
        self.store.enroll("s", root, 2)
        self.assertEqual(self.store.reserve("s", "snap-a", policy), "allowed")
        reopened = self._connect_store()
        self.assertEqual(reopened.reserve("s", "snap-a", policy), "duplicate_snapshot")
        self.assertEqual(reopened.reserve("s", "snap-b", policy), "allowed")
        self.assertEqual(reopened.reserve("s", "snap-c", policy), "automatic_limit_reached")

    def test_reenrollment_preserves_attempts_and_never_raises_the_ceiling(self) -> None:
        root = self._root()
        policy3 = self._policy(projects=(root,), limit=3)
        self.assertTrue(self.store.enroll("s", root, 1))
        self.assertEqual(self.store.reserve("s", "snap-a", policy3), "allowed")
        self.assertTrue(self.store.enroll("s", root, 3))
        self.assertEqual(self.store.reserve("s", "snap-b", policy3), "automatic_limit_reached")

    def test_reenrollment_can_lower_the_ceiling(self) -> None:
        root = self._root()
        policy = self._policy(projects=(root,), limit=2)
        self.store.enroll("s", root, 2)
        self.assertEqual(self.store.reserve("s", "snap-a", policy), "allowed")
        self.assertTrue(self.store.enroll("s", root, 1))
        self.assertEqual(self.store.reserve("s", "snap-b", policy), "automatic_limit_reached")

    def test_lower_policy_cap_and_root_revocation_deny_reservation(self) -> None:
        root = self._root()
        other = self._root("other")
        cap3 = self._policy(projects=(root,), limit=3)
        self.store.enroll("s", root, 3)
        self.assertEqual(self.store.reserve("s", "snap-a", cap3), "allowed")
        revoked = self._policy(projects=(other,), limit=3)
        self.assertEqual(self.store.reserve("s", "snap-b", revoked), "scope_not_allowed")
        lowered = self._policy(projects=(root,), limit=1)
        self.assertEqual(self.store.reserve("s", "snap-c", lowered), "automatic_limit_reached")
        self.assertEqual(self.store.reserve("s", "snap-d", cap3), "allowed")

    def test_symlinked_root_matches_the_canonical_session_scope(self) -> None:
        real = self._root("real")
        link = Path(self._dir.name) / "link"
        link.symlink_to(real)
        policy = self._policy(projects=(link,))
        approved = policy.approved_root(link)
        self.assertEqual(approved, real)
        assert approved is not None
        self.store.enroll("s", approved, 1)
        self.assertEqual(self.store.reserve("s", "snap-a", policy), "allowed")

    def test_enroll_rejects_invalid_arguments(self) -> None:
        root = self._root()
        for session_id in (None, "", 123):
            with self.subTest(session_id=session_id), self.assertRaises(ValueError):
                self.store.enroll(session_id, root, 1)
        bad_limits: tuple[Any, ...] = (0, -1, "1", 2.0, True)
        for limit in bad_limits:
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                self.store.enroll("s", root, limit)
        with self.assertRaises(ValueError):
            self.store.enroll("s", Path("relative"), 1)

    def test_reserve_rejects_an_empty_snapshot_id(self) -> None:
        root = self._root()
        policy = self._policy(projects=(root,))
        self.store.enroll("s", root, 1)
        with self.assertRaises(ValueError):
            self.store.reserve("s", "", policy)

    def test_enrollment_is_bounded_and_existing_budgets_survive_capacity(self) -> None:
        root = self._root()
        policy = self._policy(projects=(root,), limit=1)
        original = auto_store.MAX_SESSIONS
        auto_store.MAX_SESSIONS = 2
        try:
            self.assertTrue(self.store.enroll("s1", root, 1))
            self.assertTrue(self.store.enroll("s2", root, 1))
            self.assertEqual(self.store.reserve("s1", "snap-a", policy), "allowed")
            self.assertFalse(self.store.enroll("s3", root, 1))
            self.assertEqual(self.store.reserve("s2", "snap-b", policy), "allowed")
            self.assertEqual(self.store.reserve("s1", "snap-c", policy), "automatic_limit_reached")
            self.assertEqual(self.store.reserve("s3", "snap-d", policy), "missing_session")
        finally:
            auto_store.MAX_SESSIONS = original


if __name__ == "__main__":
    unittest.main()
