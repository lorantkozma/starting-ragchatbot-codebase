"""Tests that surface the hardcoded API-key bug in config.py.

The application is supposed to read ANTHROPIC_API_KEY from the environment
(.env via python-dotenv). If config.py is hardcoding a placeholder value
instead, these tests fail loudly and identify the configuration as the bug.
"""
import importlib
import os

import pytest


PLACEHOLDER_FRAGMENT = "z567890123456789012345678901234567890"


def _reload_config(monkeypatch, env_value):
    monkeypatch.setenv("ANTHROPIC_API_KEY", env_value)
    # Importing fresh so the dataclass default re-evaluates os.getenv.
    import config  # noqa: WPS433 (import inside function is intentional)

    return importlib.reload(config)


def test_anthropic_api_key_is_loaded_from_environment(monkeypatch):
    cfg_mod = _reload_config(monkeypatch, "env-key-xyz")
    assert cfg_mod.config.ANTHROPIC_API_KEY == "env-key-xyz", (
        "config.ANTHROPIC_API_KEY should reflect the ANTHROPIC_API_KEY env var. "
        "If this fails, config.py is hardcoding a value instead of reading from env."
    )


def test_anthropic_api_key_is_not_a_hardcoded_placeholder():
    import config  # noqa: WPS433

    assert PLACEHOLDER_FRAGMENT not in config.config.ANTHROPIC_API_KEY, (
        "config.ANTHROPIC_API_KEY contains a hardcoded placeholder. "
        "Restore the os.getenv('ANTHROPIC_API_KEY', '') line in backend/config.py."
    )
