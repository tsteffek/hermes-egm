"""Native Hermes plugin entrypoint; importing it performs no model calls."""

from .hermes_egm.plugin import register

__all__ = ["register"]
