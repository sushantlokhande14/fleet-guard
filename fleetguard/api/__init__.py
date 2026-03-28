"""HTTP API for the triage UI and for automation (CI can queue a campaign and poll its verdict)."""

from .app import create_app

__all__ = ["create_app"]
