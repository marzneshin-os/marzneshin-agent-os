"""Marzneshin HTTP Gateway (T3 Transport & Latency Cache — BUILD-SPEC §5.3, VS-12)."""

from .app import create_app, app

__all__ = ["create_app", "app"]
