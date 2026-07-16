"""
agent/utils.py

Shared helpers used across the agent and gateway:
- config loading (config.json)
- logging setup (logs/agent.log)
- safe_path(): confines all file operations to allowed_directories
- small result-dict helpers
"""

import json
import logging
from pathlib import Path

# Project root is the parent of the "agent" folder this file lives in.
BASE_DIR = Path(__file__).resolve().parent.parent  # .../ai_agent
CONFIG_PATH = BASE_DIR / "config.json"
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "agent.log"

_config_cache = None


def load_config():
    """Load config.json once and cache it in memory."""
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"config.json not found at {CONFIG_PATH}")

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        _config_cache = json.load(f)

    return _config_cache


def get_logger(name="ai_agent"):
    """Return a logger that writes to logs/agent.log and stdout."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    if logger.handlers:
        # Already configured (avoid duplicate handlers on repeated calls)
        return logger

    config = load_config()
    level_name = str(config.get("log_level", "info")).upper()
    level = getattr(logging, level_name, logging.INFO)
    logger.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def safe_path(path_str):
    """
    Resolve path_str to an absolute path and verify it lives inside one
    of the allowed_directories declared in config.json.

    Raises ValueError if the path is not allowed. This is the single
    choke point that keeps file_create / file_delete / file_move /
    file_list from touching anything outside the sandbox.
    """
    config = load_config()
    allowed_dirs = config.get("allowed_directories", [])

    if not allowed_dirs:
        raise ValueError(
            "No allowed_directories configured in config.json. "
            "Refusing all file operations until this is set."
        )

    target = Path(path_str).expanduser().resolve()

    for allowed in allowed_dirs:
        allowed_resolved = Path(allowed).expanduser().resolve()
        try:
            target.relative_to(allowed_resolved)
            return target  # inside an allowed directory
        except ValueError:
            continue

    raise ValueError(
        f"Path '{target}' is outside all allowed_directories. Operation refused."
    )


def ok_result(details=None):
    return {"status": "ok", "details": details}


def error_result(message):
    return {"status": "error", "details": str(message)}
