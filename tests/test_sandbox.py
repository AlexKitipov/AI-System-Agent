import pytest

from agent.actions import file_create, file_delete, file_list, file_move
from agent.utils import safe_path


def test_safe_path_allows_paths_inside_configured_directory(tmp_path, isolated_config):
    inside = tmp_path / "nested" / "file.txt"

    assert safe_path(str(inside)) == inside.resolve()


def test_safe_path_rejects_traversal_outside_configured_directory(tmp_path, isolated_config):
    outside = tmp_path.parent / "outside.txt"

    with pytest.raises(ValueError, match="outside all allowed_directories"):
        safe_path(str(tmp_path / ".." / outside.name))


def test_file_actions_are_confined_to_allowed_directory(tmp_path, isolated_config):
    source = tmp_path / "source.txt"
    moved = tmp_path / "nested" / "moved.txt"

    assert file_create(str(source), "hello") == {"status": "ok", "details": {"created": str(source)}}
    assert source.read_text(encoding="utf-8") == "hello"

    assert file_move(str(source), str(moved)) == {
        "status": "ok",
        "details": {"moved_from": str(source), "moved_to": str(moved)},
    }
    assert moved.read_text(encoding="utf-8") == "hello"

    listing = file_list(str(moved.parent))
    assert listing["status"] == "ok"
    assert listing["details"]["entries"] == [{"name": "moved.txt", "is_dir": False, "size": 5}]

    assert file_delete(str(moved)) == {"status": "ok", "details": {"deleted": str(moved)}}
    assert not moved.exists()


def test_file_actions_return_errors_for_paths_outside_allowed_directory(tmp_path, isolated_config):
    outside = tmp_path.parent / "outside.txt"

    result = file_create(str(outside), "nope")

    assert result["status"] == "error"
    assert "outside all allowed_directories" in result["details"]
