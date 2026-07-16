"""
agent/actions.py

Individual system actions. Every function returns a plain dict:
    {"status": "ok", "details": ...}
    {"status": "error", "details": ...}

Mouse/keyboard  -> pyautogui
Processes       -> psutil
Files           -> os / shutil, always routed through safe_path()
"""

import shutil
import subprocess

import psutil
import pyautogui

from .utils import safe_path, ok_result, error_result, get_logger

logger = get_logger("ai_agent.actions")

# Moving the mouse to a screen corner will raise pyautogui.FailSafeException,
# which acts as a physical kill-switch while testing.
pyautogui.FAILSAFE = True


# ---------------------------------------------------------------------
# Mouse / keyboard
# ---------------------------------------------------------------------

def move_mouse(x, y, duration=0.2):
    try:
        pyautogui.moveTo(int(x), int(y), duration=duration)
        return ok_result({"x": x, "y": y})
    except Exception as e:
        logger.exception("move_mouse failed")
        return error_result(e)


def click(button="left", x=None, y=None):
    try:
        if button not in ("left", "right", "middle"):
            return error_result(f"Invalid button '{button}'")
        if x is not None and y is not None:
            pyautogui.click(x=int(x), y=int(y), button=button)
        else:
            pyautogui.click(button=button)
        return ok_result({"button": button, "x": x, "y": y})
    except Exception as e:
        logger.exception("click failed")
        return error_result(e)


def type_text(text, interval=0.02):
    try:
        pyautogui.write(str(text), interval=interval)
        return ok_result({"typed_chars": len(str(text))})
    except Exception as e:
        logger.exception("type_text failed")
        return error_result(e)


# ---------------------------------------------------------------------
# Applications / processes
# ---------------------------------------------------------------------

# Friendly names -> real executables, so an AI can say "open paint"
# instead of needing the exact binary name.
KNOWN_APPS = {
    "notepad": "notepad.exe",
    "paint": "mspaint.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "explorer": "explorer.exe",
    "cmd": "cmd.exe",
    "terminal": "wt.exe",
}


def open_app(path_or_name):
    try:
        target = KNOWN_APPS.get(str(path_or_name).lower(), path_or_name)
        subprocess.Popen(target, shell=True)
        return ok_result({"launched": target})
    except Exception as e:
        logger.exception("open_app failed")
        return error_result(e)


def close_app(identifier):
    """identifier can be a PID (int/str) or a substring of a process name."""
    try:
        closed = []

        pid = None
        try:
            pid = int(identifier)
        except (TypeError, ValueError):
            pid = None

        for proc in psutil.process_iter(["pid", "name"]):
            name = proc.info.get("name") or ""
            if pid is not None and proc.info["pid"] == pid:
                proc.terminate()
                closed.append(proc.info)
            elif pid is None and str(identifier).lower() in name.lower():
                proc.terminate()
                closed.append(proc.info)

        if not closed:
            return error_result(f"No matching process found for '{identifier}'")
        return ok_result({"closed": closed})
    except Exception as e:
        logger.exception("close_app failed")
        return error_result(e)


def list_processes():
    try:
        procs = [p.info for p in psutil.process_iter(["pid", "name", "username"])]
        return ok_result({"processes": procs, "count": len(procs)})
    except Exception as e:
        logger.exception("list_processes failed")
        return error_result(e)


# ---------------------------------------------------------------------
# File operations (all sandboxed via safe_path)
# ---------------------------------------------------------------------

def file_create(path, content=""):
    try:
        target = safe_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)
        return ok_result({"created": str(target)})
    except Exception as e:
        logger.exception("file_create failed")
        return error_result(e)


def file_delete(path):
    try:
        target = safe_path(path)
        if not target.exists():
            return error_result(f"Path does not exist: {target}")
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        return ok_result({"deleted": str(target)})
    except Exception as e:
        logger.exception("file_delete failed")
        return error_result(e)


def file_move(src, dst):
    try:
        src_path = safe_path(src)
        dst_path = safe_path(dst)
        if not src_path.exists():
            return error_result(f"Source does not exist: {src_path}")
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_path), str(dst_path))
        return ok_result({"moved_from": str(src_path), "moved_to": str(dst_path)})
    except Exception as e:
        logger.exception("file_move failed")
        return error_result(e)


def file_list(directory):
    try:
        target = safe_path(directory)
        if not target.exists() or not target.is_dir():
            return error_result(f"Not a valid directory: {target}")
        entries = []
        for entry in target.iterdir():
            entries.append({
                "name": entry.name,
                "is_dir": entry.is_dir(),
                "size": entry.stat().st_size if entry.is_file() else None,
            })
        return ok_result({"directory": str(target), "entries": entries})
    except Exception as e:
        logger.exception("file_list failed")
        return error_result(e)
