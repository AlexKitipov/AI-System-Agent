"""
gateway/protocol.py

Defines and validates the JSON command schema used by the gateway.

Expected command format:
    {
        "action": "move_mouse",
        "params": { "x": 500, "y": 300 },
        "token": "SECRET"          <- or sent as an X-Auth-Token header instead
    }

Supported actions: move_mouse, click, type_text, open_app, close_app,
list_processes, file_create, file_delete, file_move, file_list.
(The authoritative list + required params live in agent/system_agent.py's
ACTION_MAP, so the two never drift apart.)
"""

from agent.system_agent import ACTION_MAP
from agent.utils import load_config, error_result


def validate_token(command: dict, header_token: str = None) -> bool:
    """
    Fail-closed: if no shared_secret is configured, every request is
    rejected rather than silently allowed.
    """
    config = load_config()
    expected = config.get("shared_secret")
    if not expected:
        return False

    supplied = header_token or command.get("token")
    return supplied is not None and supplied == expected


def validate_command(command: dict):
    """
    Returns (True, None) if the command shape is valid, otherwise
    (False, error_dict). Does NOT check the token -- call validate_token
    separately for that.
    """
    if not isinstance(command, dict):
        return False, error_result("Command must be a JSON object")

    action = command.get("action")
    if not action:
        return False, error_result("Missing 'action' field")

    if action not in ACTION_MAP:
        return False, error_result(f"Unknown action '{action}'")

    _, required_params = ACTION_MAP[action]
    params = command.get("params", {})
    if params is None:
        params = {}

    if not isinstance(params, dict):
        return False, error_result("'params' must be a JSON object")

    missing = [p for p in required_params if p not in params]
    if missing:
        return False, error_result(f"Missing required params: {missing}")

    return True, None
