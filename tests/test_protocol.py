from gateway.protocol import validate_command, validate_token


def test_validate_token_accepts_header_or_body_token(isolated_config):
    assert validate_token({}, header_token="test-secret") is True
    assert validate_token({"token": "test-secret"}) is True


def test_validate_token_rejects_missing_wrong_or_unconfigured_secret(isolated_config):
    assert validate_token({}) is False
    assert validate_token({"token": "wrong"}) is False

    isolated_config["shared_secret"] = ""
    assert validate_token({"token": "test-secret"}) is False


def test_validate_command_requires_object_known_action_and_params():
    assert validate_command([]) == (False, {"status": "error", "details": "Command must be a JSON object"})
    assert validate_command({"params": {}}) == (False, {"status": "error", "details": "Missing 'action' field"})
    assert validate_command({"action": "nope", "params": {}}) == (
        False,
        {"status": "error", "details": "Unknown action 'nope'"},
    )
    assert validate_command({"action": "move_mouse", "params": {"x": 10}}) == (
        False,
        {"status": "error", "details": "Missing required params: ['y']"},
    )
    assert validate_command({"action": "click", "params": []}) == (
        False,
        {"status": "error", "details": "'params' must be a JSON object"},
    )


def test_validate_command_accepts_valid_payload():
    assert validate_command({"action": "move_mouse", "params": {"x": 10, "y": 20}}) == (True, None)
    assert validate_command({"action": "click"}) == (True, None)
