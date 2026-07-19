import agent.system_agent as system_agent
from agent.system_agent import execute_command


def test_execute_command_dispatches_to_registered_action(monkeypatch):
    calls = []

    def fake_action(text):
        calls.append(text)
        return {"status": "ok", "details": {"typed_chars": len(text)}}

    monkeypatch.setitem(system_agent.ACTION_MAP, "type_text", (fake_action, ["text"]))

    result = execute_command({"action": "type_text", "params": {"text": "hello"}})

    assert result == {"status": "ok", "details": {"typed_chars": 5}}
    assert calls == ["hello"]


def test_execute_command_guards_unknown_and_missing_required_params():
    assert execute_command({"action": "missing", "params": {}}) == {
        "status": "error",
        "details": "Unknown action 'missing'",
    }
    assert execute_command({"action": "file_move", "params": {"src": "only"}}) == {
        "status": "error",
        "details": "Missing required params: ['dst']",
    }


def test_execute_command_reports_invalid_extra_params():
    result = execute_command({"action": "list_processes", "params": {"unexpected": True}})

    assert result["status"] == "error"
    assert result["details"].startswith("Invalid parameters:")
