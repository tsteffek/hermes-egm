"""Pure activation settings; automatic review is opt-in and confined to allowlisted roots."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

Activation = Literal["manual", "suggest", "auto"]
_ACTIVATIONS: tuple[Activation, ...] = ("manual", "suggest", "auto")
_SETTINGS_KEYS = frozenset({"activation", "auto_projects", "auto_max_reviews_per_session"})


class InvalidPolicy(ValueError):
    """Activation settings do not meet the policy contract."""


def _canonical_root(entry: object) -> Path:
    """Resolve one configured project to a canonical directory, or reject it."""
    if not isinstance(entry, str):
        raise InvalidPolicy("auto_projects entries must be absolute directory strings.")
    if not Path(entry).is_absolute():
        raise InvalidPolicy("auto_projects entries must be absolute paths.")
    root = Path(entry).resolve()
    if root.parent == root:
        raise InvalidPolicy("auto_projects must not name the filesystem root.")
    if not root.is_dir():
        raise InvalidPolicy("auto_projects entries must be existing directories.")
    return root


@dataclass(frozen=True)
class ActivationPolicy:
    """Validated activation settings; the default never activates automatic reviews."""

    activation: Activation
    auto_projects: tuple[Path, ...]
    auto_max_reviews_per_session: int

    @classmethod
    def parse(cls, settings: Mapping[str, object]) -> ActivationPolicy:
        if not isinstance(settings, Mapping) or any(not isinstance(key, str) for key in settings):
            raise InvalidPolicy("Activation settings must be a mapping with string keys.")
        if set(settings) - _SETTINGS_KEYS:
            raise InvalidPolicy(
                "Unrecognized activation setting; expected activation, auto_projects "
                "and auto_max_reviews_per_session."
            )
        activation = settings.get("activation", "suggest")
        if activation not in _ACTIVATIONS:
            raise InvalidPolicy("activation must be one of manual, suggest or auto.")
        projects = settings.get("auto_projects", [])
        if not isinstance(projects, list):
            raise InvalidPolicy("auto_projects must be a list of absolute directory paths.")
        roots: list[Path] = []
        for entry in projects:
            root = _canonical_root(entry)
            if root not in roots:
                roots.append(root)
        limit = settings.get("auto_max_reviews_per_session", 1)
        if type(limit) is not int:
            raise InvalidPolicy("auto_max_reviews_per_session must be an integer from 1 to 3.")
        if not 1 <= limit <= 3:
            raise InvalidPolicy("auto_max_reviews_per_session must be an integer from 1 to 3.")
        return cls(
            activation=cast(Activation, activation),
            auto_projects=tuple(roots),
            auto_max_reviews_per_session=limit,
        )

    def approved_root(self, cwd: object) -> Path | None:
        """Return the deepest allowlisted root containing cwd, or None."""
        if not isinstance(cwd, (str, Path)):
            return None
        if isinstance(cwd, str) and not cwd.strip():
            return None
        try:
            path = Path(cwd)
            if not path.is_absolute():
                return None
            resolved = path.resolve(strict=True)
            if not resolved.is_dir():
                return None
        except (OSError, ValueError):
            return None
        matches = [root for root in self.auto_projects if resolved.is_relative_to(root)]
        if not matches:
            return None
        return max(matches, key=lambda root: len(root.parts))
