"""Durable, hash-only automatic-admission ledger; pure sqlite3, no Hermes imports.

The store accepts a connection factory so the host supplies its own database
location. Each supplied connection is prepared, used under an explicit
``BEGIN IMMEDIATE`` transaction, and always closed here. Only SHA-256
identifiers and integer counters/ceilings are persisted; raw paths, document
text, model output and credentials never reach the database.
"""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from .policy import ActivationPolicy

Admission = Literal[
    "allowed",
    "automatic_disabled",
    "missing_session",
    "scope_not_allowed",
    "duplicate_snapshot",
    "automatic_limit_reached",
]

MAX_SESSIONS = 10_000
_BUSY_TIMEOUT_MS = 5_000
_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_hash TEXT PRIMARY KEY,
    root_hash TEXT NOT NULL,
    ceiling INTEGER NOT NULL,
    attempts INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS snapshots (
    session_hash TEXT NOT NULL,
    snapshot_hash TEXT NOT NULL,
    PRIMARY KEY (session_hash, snapshot_hash)
);
"""


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _root_key(root: Path) -> str:
    return _sha256(str(root))


def _prepare(connection: sqlite3.Connection) -> None:
    """Take manual transaction control, bound lock waits, and ensure the schema."""
    connection.isolation_level = None
    connection.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
    # Preserve the host helper's journal-mode choice (including safe WAL fallbacks).
    connection.executescript(_SCHEMA)


class AutoReviewStore:
    """Session-scoped automatic-review budget enforced atomically across processes."""

    def __init__(self, connect: Callable[[], sqlite3.Connection]) -> None:
        self._connect = connect

    def enroll(self, session_id: object, approved_root: Path, limit: int) -> bool:
        """Enroll or recognize the same session/root without renewing its budget.

        Repeated enrollment never resets attempts and never raises the ceiling:
        the stored ceiling is lowered to ``min(existing, limit)`` when needed but
        never increased, and the original approved root is retained.
        """
        if not isinstance(session_id, str) or not session_id:
            raise ValueError("session_id must be a non-empty string.")
        if not isinstance(approved_root, Path) or not approved_root.is_absolute():
            raise ValueError("approved_root must be an absolute Path.")
        if type(limit) is not int or limit < 1:
            raise ValueError("limit must be a positive integer.")
        session_hash = _sha256(session_id)
        root_hash = _root_key(approved_root)
        connection = self._connect()
        try:
            _prepare(connection)
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    "SELECT ceiling, root_hash FROM sessions WHERE session_hash = ?",
                    (session_hash,),
                ).fetchone()
                if row is None:
                    if self._at_capacity(connection):
                        connection.execute("ROLLBACK")
                        return False
                    connection.execute(
                        "INSERT INTO sessions (session_hash, root_hash, ceiling, attempts) "
                        "VALUES (?, ?, ?, 0)",
                        (session_hash, root_hash, limit),
                    )
                    connection.execute("COMMIT")
                    return True
                if str(row[1]) != root_hash:
                    connection.execute("ROLLBACK")
                    return False
                existing_ceiling = int(row[0])
                if limit < existing_ceiling:
                    connection.execute(
                        "UPDATE sessions SET ceiling = ? WHERE session_hash = ?",
                        (limit, session_hash),
                    )
                connection.execute("COMMIT")
                return True
            except BaseException:
                connection.execute("ROLLBACK")
                raise
        finally:
            connection.close()

    def reserve(self, session_id: object, snapshot_id: str, policy: ActivationPolicy) -> Admission:
        """Atomically authorize one automatic review and record the attempt.

        The attempt is committed before any model work, so a later failure or
        cancellation is never refunded. Denials never write to the ledger.
        """
        if policy.activation != "auto":
            return "automatic_disabled"
        if not isinstance(session_id, str) or not session_id:
            return "missing_session"
        if not isinstance(snapshot_id, str) or not snapshot_id:
            raise ValueError("snapshot_id must be a non-empty string.")
        session_hash = _sha256(session_id)
        snapshot_hash = _sha256(snapshot_id)
        allowed_roots = {_root_key(root) for root in policy.auto_projects}
        connection = self._connect()
        try:
            _prepare(connection)
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    "SELECT root_hash, ceiling, attempts FROM sessions WHERE session_hash = ?",
                    (session_hash,),
                ).fetchone()
                if row is None:
                    connection.execute("ROLLBACK")
                    return "missing_session"
                if str(row[0]) not in allowed_roots:
                    connection.execute("ROLLBACK")
                    return "scope_not_allowed"
                duplicate = connection.execute(
                    "SELECT 1 FROM snapshots WHERE session_hash = ? AND snapshot_hash = ?",
                    (session_hash, snapshot_hash),
                ).fetchone()
                if duplicate is not None:
                    connection.execute("ROLLBACK")
                    return "duplicate_snapshot"
                effective_cap = min(int(row[1]), policy.auto_max_reviews_per_session)
                if int(row[2]) >= effective_cap:
                    connection.execute("ROLLBACK")
                    return "automatic_limit_reached"
                connection.execute(
                    "INSERT INTO snapshots (session_hash, snapshot_hash) VALUES (?, ?)",
                    (session_hash, snapshot_hash),
                )
                connection.execute(
                    "UPDATE sessions SET attempts = attempts + 1 WHERE session_hash = ?",
                    (session_hash,),
                )
                connection.execute("COMMIT")
                return "allowed"
            except BaseException:
                connection.execute("ROLLBACK")
                raise
        finally:
            connection.close()

    @staticmethod
    def _at_capacity(connection: sqlite3.Connection) -> bool:
        row = connection.execute("SELECT COUNT(*) FROM sessions").fetchone()
        return row is not None and int(row[0]) >= MAX_SESSIONS
