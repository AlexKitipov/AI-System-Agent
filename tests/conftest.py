"""Test fixtures that keep OS-touching integrations mocked out."""

from __future__ import annotations

import sys
import types

import pytest

# pyautogui and psutil are optional in CI and must never touch the real OS during tests.
psutil_stub = types.ModuleType("psutil")
psutil_stub.process_iter = lambda *args, **kwargs: iter(())
sys.modules.setdefault("psutil", psutil_stub)

pyautogui_stub = types.ModuleType("pyautogui")
pyautogui_stub.FAILSAFE = True
pyautogui_stub.moveTo = lambda *args, **kwargs: None
pyautogui_stub.click = lambda *args, **kwargs: None
pyautogui_stub.write = lambda *args, **kwargs: None
sys.modules.setdefault("pyautogui", pyautogui_stub)

from agent import utils

# Make importing action modules independent from an untracked local config.json.
utils._config_cache = {
    "shared_secret": "test-secret",
    "allowed_directories": ["/tmp"],
    "log_level": "critical",
}


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch, tmp_path):
    """Provide a safe config for modules that read config.json at runtime."""
    config = {
        "shared_secret": "test-secret",
        "allowed_directories": [str(tmp_path)],
        "log_level": "critical",
    }
    monkeypatch.setattr(utils, "_config_cache", config)
    yield config
    monkeypatch.setattr(utils, "_config_cache", None)
