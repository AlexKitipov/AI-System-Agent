"""
agent/system_agent.py

The local "daemon" logic. Note: this module does NOT open any socket or
network port itself -- it's imported directly by gateway/server.py and
called in-process. This keeps the whole system to a single Python
process, which is simpler and avoids a second layer of unauthenticated
local IPC.

Every command that reaches execute_command() has already passed through
gateway/protocol.py's token + schema validation.
"""

from . import actions
from .utils import get_logger, error_result

logger = get_logger("ai_agent.system_agent")

# action name -> (function, [required param names])
ACTION_MAP = {
    "move_mouse":      (actions.move_mouse,      ["x", "y"]),
    "click":           (actions.click,           []),
    "type_text":       (actions.type_text,       ["text"]),
    "open_app":        (actions.open_app,        ["path_or_name"]),
    "close_app":       (actions.close_app,       ["identifier"]),
    "list_processes":  (actions.list_processes,  []),
    "file_create":      (actions.file_create,      ["path"]),
    "file_delete":      (actions.file_delete,      ["path"]),
    "file_move":        (actions.file_move,        ["src", "dst"]),
    "file_list":        (actions.file_list,        ["directory"]),
}


def execute_command(command: dict) -> dict:
    """
    command example:
        {
            "action": "move_mouse",
            "params": {"x": 500, "y": 300}
        }
    """
    action_name = command.get("action")
    params = command.get("params") or {}

    logger.info("Executing action=%s params=%s", action_name, params)

    if action_name not in ACTION_MAP:
        logger.warning("Unknown action requested: %s", action_name)
        return error_result(f"Unknown action '{action_name}'")

    func, required_params = ACTION_MAP[action_name]

    missing = [p for p in required_params if p not in params]
    if missing:
        logger.warning("Missing params for %s: %s", action_name, missing)
        return error_result(f"Missing required params: {missing}")

    try:
        result = func(**params)
        logger.info("Result for %s: %s", action_name, result)
        return result
    except TypeError as e:
        logger.exception("Bad params for %s", action_name)
        return error_result(f"Invalid parameters: {e}")
    except Exception as e:
        logger.exception("Unhandled error executing %s", action_name)
        return error_result(str(e))
