# AI System Agent

A local, AI-controllable automation agent for Windows. It exposes a small
HTTP/WebSocket gateway on your machine so an AI assistant (Copilot, GPT,
Gemini, or Claude itself) can send it JSON commands to move the mouse,
type text, open/close apps, list processes, and manage files inside a
directory sandbox you define.

**Nothing in this project connects to any AI service.** It's purely the
receiving end — you point an AI (or your own scripts) at it.

## Project layout

```
ai_agent/
  agent/
    system_agent.py   # command dispatcher (no network port of its own)
    actions.py         # the actual mouse/keyboard/process/file actions
    utils.py            # config loading, logging, path sandboxing
  gateway/
    server.py          # FastAPI app -> the thing you actually run
    protocol.py         # JSON schema + token validation
  frontend/
    index.html          # manual test console
    app.js
  config.example.json  # template; copy to config.json locally
  run_all.bat
  README.md
```

## 1. Install dependencies

```bash
pip install fastapi uvicorn pyautogui psutil
```

You'll also want `uvicorn[standard]` for WebSocket support, though plain
`uvicorn` works for the HTTP endpoint:

```bash
pip install "uvicorn[standard]"
```

## 2. Configure `config.json`

`config.json` is intentionally ignored by git because it contains your local secret and machine-specific paths. Create it from the checked-in template before starting the server:

```bash
cp config.example.json config.json
```

On Windows PowerShell, use:

```powershell
Copy-Item config.example.json config.json
```

Then edit `config.json` with your own secret and allowed directories:

```json
{
  "gateway_port": 8765,
  "shared_secret": "CHANGE_ME_TO_A_RANDOM_SECRET",
  "allowed_directories": [
    "C:/Users/YourUser/Desktop",
    "D:/Projects"
  ],
  "log_level": "info"
}
```

- **`shared_secret`** — change this to a random string. Every request must
  include it, or it's rejected. There is no default/bypass; if this field
  is empty, the server refuses *all* commands.
- **`allowed_directories`** — the only folders `file_create`, `file_delete`,
  `file_move`, and `file_list` are allowed to touch. Anything outside
  these paths is refused, no matter what a command asks for.

## 3. Run it

From the `ai_agent/` folder:

```bash
python -m uvicorn gateway.server:app --host 127.0.0.1 --port 8765
```

Or just double-click **`run_all.bat`**, which does the same thing.

> There's no separate step to "start the agent" — `system_agent.py` has
> no network port of its own. It's imported directly by `gateway/server.py`
> and runs in the same process, which is why one command starts everything.

You should see:

```
AI System Agent Gateway
Listening on http://127.0.0.1:8765
```

Logs are written to `logs/agent.log`. The `logs/` directory is a local runtime artifact and is not tracked by git.

## 4. Test it manually

Open `frontend/index.html` directly in a browser (double-click it, no
server needed for the page itself). Enter your `shared_secret` in the
**Token** field, paste a JSON command, and click **Send command**.

## 5. Example commands

Move the mouse:
```json
{ "action": "move_mouse", "params": { "x": 500, "y": 300 } }
```

Click:
```json
{ "action": "click", "params": { "button": "left" } }
```

Type text (e.g. into whatever window currently has focus):
```json
{ "action": "type_text", "params": { "text": "Hello from the AI agent" } }
```

Open Paint:
```json
{ "action": "open_app", "params": { "path_or_name": "paint" } }
```

Create a file inside an allowed directory:
```json
{
  "action": "file_create",
  "params": {
    "path": "C:/Users/YourUser/Desktop/note.txt",
    "content": "Created by the AI agent"
  }
}
```

List processes:
```json
{ "action": "list_processes", "params": {} }
```

Full action list: `move_mouse`, `click`, `type_text`, `open_app`,
`close_app`, `list_processes`, `file_create`, `file_delete`, `file_move`,
`file_list`.

## 6. How another AI connects

Point it at:

```
POST http://127.0.0.1:8765/command
Content-Type: application/json
X-Auth-Token: CHANGE_ME_SECRET

{ "action": "move_mouse", "params": { "x": 500, "y": 300 } }
```

The token can go either in the `X-Auth-Token` header (shown above) or as
a `"token"` field inside the JSON body — useful for the WebSocket
endpoint at `ws://127.0.0.1:8765/ws`, which doesn't support custom
headers from a browser client.

Response shape is always:
```json
{ "status": "ok", "details": { ... } }
```
or
```json
{ "status": "error", "details": "..." }
```

## 7. Autostart on Windows

- **Manual (VS Code terminal):** run the command from step 3 directly.
- **`run_all.bat`:** double-click it, or run it from a terminal. Make sure you have created your local `config.json` first.
- **Start on boot:** press `Win+R`, type `shell:startup`, and drop a
  shortcut to `run_all.bat` in the folder that opens. It'll launch (with
  a visible console window) every time you log in.

## Security notes — read before exposing this to anything

- The server binds to **`127.0.0.1` only**. It is never reachable from
  other devices on your network, regardless of firewall settings.
- Every command requires the `shared_secret` from your local, gitignored
  `config.json`. Change the template value before running this for real, and
  do not commit your local config.
- File operations are hard-sandboxed to `allowed_directories` via
  `agent/utils.py::safe_path`. There's no code path that lets a command
  escape that sandbox — if `allowed_directories` is empty, all file
  operations are refused outright.
- `open_app` and `close_app` are **not** sandboxed — by design, this
  agent can launch and kill arbitrary programs on your machine (that's
  the point). Keep your `shared_secret` private, since anyone who has it
  can act as you on this machine while the gateway is running.
- `pyautogui.FAILSAFE` is enabled: physically slamming your mouse cursor
  into a screen corner aborts any in-progress `pyautogui` action as a
  manual kill switch.
- This project intentionally does not include a remote/internet-facing
  mode. If you ever want an AI running elsewhere to control this
  machine, that requires a deliberate, separate design (tunneling,
  proper auth, etc.) — don't just change the bind address to `0.0.0.0`.
