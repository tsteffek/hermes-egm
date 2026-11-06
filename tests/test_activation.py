"""Exercise policy admission through the real handler and a real temporary SQLite DB."""

import asyncio
import importlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_plugin import Context
from test_runner import FakeLlm


def arguments(text="Design the smallest useful feature.", *, automatic: object = True):
    return {
        "target": "spec",
        "documents": [{"id": "spec", "text": text}],
        "lenses": ["design"],
        "automatic": automatic,
    }


class ActivationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.plugin = importlib.import_module("hermes_egm.plugin")
        self.assertTrue(hasattr(self.plugin, "open_state_db"), "automatic admission is missing")
        self.temp = tempfile.TemporaryDirectory(prefix="egm-activation-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.database = self.root / "state.sqlite3"
        self.db_patch = patch.object(
            self.plugin, "open_state_db", side_effect=lambda: sqlite3.connect(self.database)
        )
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)

    def setup_context(self, **settings):
        ctx = Context(
            {
                "activation": "auto",
                "auto_projects": [str(self.root)],
                "auto_max_reviews_per_session": 1,
                **settings,
            }
        )
        self.plugin.register(ctx)
        guidance = ctx.sections["hermes-egm.activation"](
            {
                "session_id": "trusted-session",
                "cwd": str(self.root),
            }
        )
        return ctx, guidance, ctx.tools["egm_review"]["handler"]

    async def test_automatic_review_uses_trusted_session_and_never_forwards_policy_context(self):
        ctx, guidance, handler = self.setup_context()
        self.assertIn("automatic=true", guidance)
        first = json.loads(
            await handler(
                arguments(),
                session_id="trusted-session",
                parent_agent="PRIVATE_PARENT_CANARY",
                user_task="PRIVATE_HISTORY_CANARY",
            )
        )
        self.assertEqual(first["status"], "complete")
        self.assertTrue(first["automatic"])
        duplicate = json.loads(await handler(arguments(), session_id="trusted-session"))
        self.assertEqual(duplicate["status"], "skipped")
        self.assertEqual(duplicate["reason"], "duplicate_snapshot")
        changed = json.loads(
            await handler(arguments("Different draft."), session_id="trusted-session")
        )
        self.assertEqual(changed["reason"], "automatic_limit_reached")
        self.assertEqual(len(ctx.llm.calls), 1)
        sent = str(ctx.llm.calls)
        for private in (
            "PRIVATE_PARENT_CANARY",
            "PRIVATE_HISTORY_CANARY",
            "trusted-session",
            str(self.root),
        ):
            self.assertNotIn(private, sent)
        self.assertNotIn("EGM activation", sent)

    async def test_missing_or_forged_session_cannot_authorize_automatic_review(self):
        ctx, _, handler = self.setup_context()
        for kwargs in ({}, {"session_id": "not-enrolled"}):
            result = json.loads(await handler(arguments(), **kwargs))
            self.assertEqual(result["status"], "skipped")
            self.assertEqual(result["reason"], "missing_session")
        forged = json.loads(await handler({**arguments(), "session_id": "trusted-session"}))
        self.assertEqual(forged["status"], "invalid_input")
        self.assertEqual(ctx.llm.calls, [])

    async def test_suggest_manual_and_unscoped_auto_make_no_automatic_calls(self):
        cases = [
            {"activation": "manual"},
            {"activation": "suggest"},
            {"auto_projects": []},
        ]
        for settings in cases:
            with self.subTest(settings=settings):
                ctx, guidance, handler = self.setup_context(**settings)
                self.assertIn("automatic=false", guidance)
                result = json.loads(await handler(arguments(), session_id="not-enrolled"))
                self.assertEqual(result["status"], "skipped")
                self.assertEqual(ctx.llm.calls, [])

    async def test_revocation_is_checked_at_call_time(self):
        ctx, _, handler = self.setup_context()
        ctx.settings["auto_projects"] = []
        revoked = json.loads(await handler(arguments(), session_id="trusted-session"))
        self.assertEqual(revoked["reason"], "scope_not_allowed")
        ctx.settings["activation"] = "suggest"
        disabled = json.loads(await handler(arguments(), session_id="trusted-session"))
        self.assertEqual(disabled["reason"], "automatic_disabled")
        self.assertEqual(ctx.llm.calls, [])

    async def test_invalid_input_does_not_consume_the_automatic_budget(self):
        ctx, _, handler = self.setup_context()
        bad = json.loads(await handler({"automatic": True}, session_id="trusted-session"))
        self.assertEqual(bad["status"], "invalid_input")
        good = json.loads(await handler(arguments(), session_id="trusted-session"))
        self.assertEqual(good["status"], "complete")
        self.assertEqual(len(ctx.llm.calls), 1)

    async def test_storage_failure_blocks_auto_but_not_explicit_manual_review(self):
        with patch.object(self.plugin, "open_state_db", side_effect=OSError("PRIVATE_DB_ERROR")):
            ctx, guidance, handler = self.setup_context()
            self.assertIn("unavailable", guidance)
            blocked = json.loads(await handler(arguments(), session_id="trusted-session"))
            self.assertEqual(blocked["status"], "skipped")
            self.assertEqual(blocked["reason"], "automatic_policy_unavailable")
            self.assertNotIn("PRIVATE_DB_ERROR", str(blocked))
            manual = json.loads(await handler(arguments(automatic=False)))
            self.assertEqual(manual["status"], "complete")
            self.assertFalse(manual["automatic"])
            self.assertEqual(len(ctx.llm.calls), 1)

    async def test_rebuilding_prompt_preserves_auto_guidance_without_resetting_budget(self):
        ctx, first_guidance, handler = self.setup_context()
        first = json.loads(await handler(arguments(), session_id="trusted-session"))
        self.assertEqual(first["status"], "complete")
        rebuilt = ctx.sections["hermes-egm.activation"](
            {
                "session_id": "trusted-session",
                "cwd": str(self.root),
            }
        )
        self.assertEqual(rebuilt, first_guidance)
        denied = json.loads(await handler(arguments("Another draft"), session_id="trusted-session"))
        self.assertEqual(denied["reason"], "automatic_limit_reached")
        self.assertEqual(len(ctx.llm.calls), 1)

    async def test_automatic_marker_is_strict_boolean(self):
        ctx, _, handler = self.setup_context()
        for bad in ("true", "false", 1, 0, None):
            with self.subTest(bad=bad):
                result = json.loads(
                    await handler(arguments(automatic=bad), session_id="trusted-session")
                )
                self.assertEqual(result["status"], "invalid_input")
        self.assertEqual(ctx.llm.calls, [])

    async def test_cancellation_does_not_refund_an_admitted_automatic_attempt(self):
        class CancelledLlm(FakeLlm):
            async def acomplete_structured(self, **kwargs):
                self.calls.append(kwargs)
                raise asyncio.CancelledError()

        ctx, _, handler = self.setup_context()
        ctx.llm = CancelledLlm()
        with self.assertRaises(asyncio.CancelledError):
            await handler(arguments(), session_id="trusted-session")
        retry = json.loads(
            await handler(arguments("Changed after cancel."), session_id="trusted-session")
        )
        self.assertEqual(retry["reason"], "automatic_limit_reached")
        self.assertEqual(len(ctx.llm.calls), 1)
