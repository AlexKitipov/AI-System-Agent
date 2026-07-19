# AI‑System‑Agent — Full Technical Audit & Development Roadmap

**Repository:** github.com/AlexKitipov/AI-System-Agent
**Audit basis:** direct download and inspection of the `main` branch (not summary/memory) — `agent/`, `gateway/`, `frontend/`, `config.json`, `cronos.ps1`, `logs/agent.log`, `README.md`, `REPOSITORY OVERVIEW.md`, `Browser-Based AI Chat Integration.md`.

---

## 1. High‑Level System Overview

**Purpose:** AI‑System‑Agent is a local Windows automation gateway. It exposes a small FastAPI HTTP/WebSocket server on `127.0.0.1:8765` that accepts structured JSON commands and executes them against the local machine — moving the mouse, clicking, typing text, opening/closing applications, listing processes, and doing sandboxed file operations. It's designed so an external AI assistant (or any script) can drive the machine by sending JSON, without that AI needing any local access of its own.

**Architecture (as built):**

```
Caller (frontend/index.html, cronos.ps1, or an external AI)
        │  JSON over HTTP POST /command  or  WebSocket /ws
        ▼
gateway/server.py   (FastAPI, binds 127.0.0.1 only)
        │  validate_token() → validate_command()   [gateway/protocol.py]
        ▼
agent/system_agent.py :: execute_command()   (ACTION_MAP dispatch table)
        │
        ▼
agent/actions.py   (pyautogui / psutil / os·shutil, file ops routed through safe_path())
        │
        ▼
agent/utils.py     (config.json loader, logger, safe_path sandbox)
```

It is a **single Python process** — `system_agent.py` has no socket of its own; it's imported directly by `server.py` and called in-process. This is a deliberate simplification versus the original two-process design in the prompt that generated it, and it's a reasonable one: it removes a second layer of unauthenticated local IPC that would otherwise need its own auth story.

**Design philosophy:** localhost-only, fail-closed token auth, and a directory allowlist (`safe_path()`) as the three pillars of safety. The intent is clearly "give an AI hands, but only on this machine, only with a shared secret, and only inside folders I named." That's a sound default posture for this category of tool.

**Intended use case:** the two extra documents already in the repo (`Browser-Based AI Chat Integration.md`, `REPOSITORY OVERVIEW.md`) make the actual goal explicit — this is meant to become the execution backend for a **browser-based chat UI that an external AI (Copilot/GPT/Gemini/Claude) drives conversationally**, not just a JSON test console. That target isn't built yet; today the system only accepts pre-formed JSON, not natural language. That gap is the single biggest thing separating the current repo from the user's stated goal, and it's assessed in detail in Sections 4 and 7.

---

## 2. Codebase Audit

**Code quality / structure:** The codebase is small (≈460 lines across 5 Python files) and unusually clean for its size — one responsibility per file, one `ACTION_MAP` as the single source of truth for both `system_agent.py`'s dispatch and `protocol.py`'s schema validation (so the two can't drift apart), and consistent `{"status": "ok"/"error", "details": ...}` return shapes throughout. Naming is consistent (`file_*`, `*_app`, snake_case throughout). This is a genuine strength — for a repo this size, over-abstraction would be a bigger risk than under-abstraction, and it avoids that trap.

**Separation of concerns:** Good. `utils.py` (config/logging/sandboxing) is cleanly separate from `actions.py` (the actual OS calls), which is separate from `system_agent.py` (dispatch/validation) and `protocol.py`/`server.py` (transport). No file reaches into another's internals.

**Error handling:** Every action function wraps its body in `try/except Exception`, logs via `logger.exception`, and returns a structured error — no unhandled exceptions can escape to the caller as a raw 500. The one blanket-except pattern to flag: catching bare `Exception` everywhere means a genuine bug (e.g., a `TypeError` from bad internal logic) looks identical, from the caller's perspective, to an expected failure (e.g., file not found). There's no error *code*, only a human-readable string in `details` — fine for a human reading logs, brittle for any future automated retry logic that wants to distinguish "path not allowed" from "disk full."

**Logging:** Centralized through `utils.get_logger()`, writes to both `logs/agent.log` and stdout, level driven by `config.json`. Reasonable. Two concrete issues:
- Every command's full `params` dict is logged at INFO level with no redaction. If a future command ever carries something sensitive (a password typed via `type_text`, a token embedded in a file's content via `file_create`), it lands in plaintext in `agent.log`.
- **`logs/agent.log` is currently committed to the git repository.** It contains real local timestamps, real command history, and one real Windows file path (`C:/Users/Alex Kitipov/Documents/Notes`) inside a logged traceback. This should not be tracked by git — see Security Review, Finding 1, this is the most concrete/actionable finding in this whole audit.

**Security practices:**
- Fail-closed token check (`validate_token` returns `False` if `shared_secret` is unset) is a good default — most homegrown auth gets this backwards.
- Localhost-only binding is hardcoded correctly in both the `__main__` uvicorn call and documented in comments.
- Token comparison uses plain `==` (`gateway/protocol.py`), which is not constant-time. On localhost this is a low-severity theoretical issue (timing attacks need many precise samples, hard to get over an OS network stack for a 20+ char secret), but it's a one-line fix (`hmac.compare_digest`) worth taking for free.
- **The committed `config.json` still has `"shared_secret": "CHANGE_ME_SECRET"`.** Since this file is tracked in a public repo, the placeholder secret is public. If this exact config is ever deployed unmodified, anyone who has read the repo has full control of the machine while the gateway runs. This is flagged again under Security Review because it's the highest-severity finding in the whole audit.
- `config.json` also has **real personal directory paths with the account name in them** (`C:/Users/Alex Kitipov/Desktop`, `.../Downloads`, `.../Documents`) committed to a public repository. `cronos.ps1` has the same path baked in. This isn't a security hole in the *software*, but it is unnecessary personal information disclosure in a public repo.

**Sandbox isolation / allowed-directories logic (`utils.safe_path`):** The core mechanism — resolve the target path, then check `target.relative_to(allowed_dir)` for each configured allowed directory — is correct and simple, and it fails closed when `allowed_directories` is empty. Two real gaps:
1. **No symlink/junction defense.** `Path.resolve()` does follow symlinks on the *target* path itself, but there's no check that stops someone from creating a symlink/junction *inside* an allowed directory that points outside it (e.g., an allowed-dir file that's actually a junction to `C:\Windows\System32`). `file_create`/`file_delete` would then operate on the junction target, not the allowed directory. This is a real, if narrow, sandbox-escape vector.
2. **`open_app` and `close_app` are entirely outside the sandbox by design** (documented as intentional in the README), which is defensible for the tool's purpose but means the "sandboxed" framing only applies to the file-operations quarter of the action surface, not the whole system. Worth stating explicitly in docs rather than leaving implicit.

**Token validation:** Correctly fail-closed, correctly checked before schema validation, correctly supports both header and body token placement. Missing: no token expiry, no per-token scoping (every valid token can do everything), no revocation mechanism short of editing `config.json` and restarting the process.

**HTTP/WebSocket server design:** Idiomatic FastAPI. `/health`, `/command`, `/ws` are minimal and correct. One inconsistency worth fixing: the HTTP path supports the token via header *or* body, but the WebSocket path only accepts it in the message body (documented, but it means a caller migrating from HTTP to WS has to change how it sends auth, not just the transport). CORS is wide open (`allow_origins=["*"]`) — justified in a comment as safe because the bind is localhost-only, which is true today, but is a latent risk if anyone later changes the bind address without also revisiting CORS (a classic "the two decisions get made independently by different future-yous" problem).

**Windows automation layer:**
- `open_app` uses `subprocess.Popen(target, shell=True)` with the caller-supplied string passed straight through. Since `open_app` isn't sandboxed and its whole purpose is to launch arbitrary named programs, this is "working as intended" rather than an oversight — but `shell=True` specifically means shell metacharacters (`&`, `|`, `;`, backticks under cmd.exe parsing rules) in a crafted `path_or_name` value are interpreted by the shell, not just treated as a filename. Given any caller who's already passed the token check is *already* fully trusted to launch/kill arbitrary processes, this doesn't add a new trust boundary — but it does turn "launch one program" into "run an arbitrary shell command line," which is a bigger blast radius than the action's name suggests, and worth closing off if the token is ever shared more broadly than "just me."
- `close_app`'s substring-match-by-name path (`str(identifier).lower() in name.lower()`) can terminate multiple processes on a loose match (e.g., `"code"` matches every `Code.exe` and `Code Helper` process). No confirmation, no "matched N processes, did you mean this?" step — it just kills all of them. That's a footgun for an AI caller that isn't perfectly precise about identifiers.
- No timeout on any action. A hung `pyautogui` call (e.g., waiting on a modal dialog that never appears) or a slow file operation on a network drive blocks that request indefinitely; because there's no async offloading (`execute_command` runs synchronously inside the async FastAPI handler), a long-hanging action also blocks the single-process event loop for every other in-flight request. This is a real design constraint the current single-process model surfaces.

**Risky patterns / duplication / bugs:**
- No duplicated logic — flagged above as a genuine strength.
- No outdated constructs; uses `pathlib`, type-annotated function signatures (partially), modern FastAPI idioms.
- One latent bug: `move_mouse`/`click` cast `x`/`y` with `int(x)` inside a `try` that also catches the cast failure and reports it as a generic action failure rather than a parameter-validation failure — functionally fine, but it means "you sent a string for x" and "pyautogui threw" look identical in the response.
- `__pycache__/*.pyc` files are committed to the repo (visible in the tree under `agent/__pycache__` and `gateway/__pycache__`). Harmless but sloppy; there's no `.gitignore` in the repo at all.

---

## 3. Architecture Review

**Project layout:** Flat and legible for the current size (2 packages, 5 modules). It will not scale past the chat-integration goal without new boundaries — the `Browser-Based AI Chat Integration.md` doc already anticipates this correctly (proposing `gateway/middleware/`, `agent/nlu_engine.py`, `tests/`, `docs/`).

**Module boundaries:** Clean today because `ACTION_MAP` is the one shared contract. The risk is that it's a single dict living in `system_agent.py` that both dispatch *and* schema validation import from — convenient now, but it means adding any per-action metadata (rate limits, required scopes, whether an action needs confirmation) means growing that dict's value tuples, which will get unwieldy past ~15-20 actions.

**API design:** `/command` and `/ws` are both thin passthroughs to the same `execute_command`, which is good consistency. There's no API versioning, no `/actions` introspection endpoint (a caller — especially an AI — has no way to *discover* the action list and required params other than reading the source or getting an error back). That's a real gap for the "external AI drives this" use case: the AI has to already know the exact schema.

**Command execution pipeline:** Linear and easy to reason about: validate token → validate schema → dispatch → execute → log → respond. No queueing, no concurrency control, no execution history. Fine for single-caller interactive use; will not hold up if two callers (e.g., a human via the test frontend and an AI via `/ws`) send overlapping mouse/keyboard commands — there's no lock, so their actions interleave physically on the same mouse cursor.

**Sandbox enforcement:** Centralized in one function (`safe_path`), which is the right pattern — every file action calls the same choke point rather than reimplementing checks. The symlink gap noted above is the main weakness in an otherwise sound design.

**Extensibility:** Adding a new action today means: write the function in `actions.py`, add one line to `ACTION_MAP`. That's about as low-friction as it gets, and it's worth explicitly preserving in any refactor rather than "improving" into something heavier.

**Maintainability:** High for the current size. The main maintainability risk is that non-code artifacts (two large AI-generated planning docs, a personal `.ps1` script, committed logs/pycache) are sitting in the repo root, at the same level as the actual source. That makes the repo noisier to navigate than the code itself warrants.

**Scalability:** Not a bottleneck at the "one user, one machine" scope this is designed for. It would become one the moment multiple concurrent callers or remote (non-localhost) access enter the picture — neither of which the current design should be stretched to cover without a real redesign (see Roadmap).

**Suggested improvements:**
- **Command registry as a small decorator-based registry instead of a hand-maintained dict**, e.g. each action self-registers with its name, required params, and (new) a `sandboxed: bool` / `destructive: bool` flag — keeps the "add one function" ergonomics while giving you metadata to hang new checks off of.
- **Config system:** move from a single flat `config.json` to layered config (defaults in code, overridden by `config.json`, overridden by environment variables for the secret specifically) so the token never has to live in a file that could be accidentally committed — see Security Review Finding 1.
- **Safer automation layer:** add a per-request or per-session lock around `pyautogui` calls so two callers can't interleave physical mouse/keyboard input; add a configurable timeout per action.
- **More robust sandboxing:** resolve and re-check symlink targets, not just the literal requested path; consider also blocking well-known sensitive Windows paths (`System32`, `Program Files`, the Windows directory itself) even if they somehow end up inside an allowed directory by config mistake — defense in depth.
- **Plugin system for new commands:** genuinely useful *once* the action count grows past what a single file comfortably holds (rough rule of thumb: past 20-25 actions, or once actions need to live in separate files for domain reasons like "browser control" vs "file ops" vs "OS control"). Not urgent today — the current flat file is still easy to read.

---

## 4. Missing Features & Opportunities

Grouped by how directly each one blocks the user's stated goal (external AI ↔ chat UI ↔ local agent), based on cross-referencing the code against both the original prompt and the two analysis docs already in the repo:

**Directly blocking the stated chat-integration goal:**
- **Natural-language-to-command translation.** Today the system only accepts pre-formed `{"action": ..., "params": {...}}` JSON. An external AI *can* produce that JSON itself (many can, given the schema) — so this may be less blocking than the in-repo analysis doc suggests, if the plan is "the AI formats the JSON" rather than "the server parses English." Worth explicitly deciding which of those two models this is, since they lead to very different next steps.
- **Chat-shaped frontend.** `frontend/index.html` is a JSON test console, not a conversational UI — no message history, no distinction between user/AI/system messages.
- **Action introspection endpoint** (e.g., `GET /actions`) so a caller (human or AI) can learn the schema without reading source.

**Missing safety checks:**
- No rate limiting on `/command` or `/ws` — nothing stops a runaway loop (buggy AI or script) from firing thousands of mouse clicks per second.
- No command whitelisting/allowlisting *per token* — every valid token can do everything; there's no way to issue a "read-only" or "no file-delete" token.
- No confirmation step for destructive actions (`file_delete`, `close_app`) — every other local-automation tool in this space (browser extensions with page control, RPA tools) gates destructive actions behind an extra check; this one doesn't.
- No token expiration/rotation.

**Missing logging / observability:**
- No structured audit trail (who — which token/session — did what, when), just a flat text log.
- No metrics/health detail beyond a bare `{"status": "ok"}` on `/health` (no uptime, no last-command time, no error rate).

**Missing config:**
- No `.gitignore` at all — this is the most concrete quick-fix in this whole report (see Roadmap, High Priority).
- No `requirements.txt` / `pyproject.toml` in the repo — dependencies (`fastapi`, `uvicorn`, `pyautogui`, `psutil`) are only mentioned in the README's prose, not pinned anywhere machine-readable.

**Missing documentation:**
- README is solid for setup/usage but doesn't document the symlink caveat, the `open_app`/`close_app` sandbox exception, or the single-process concurrency constraint.
- No `CHANGELOG.md`, no `CONTRIBUTING.md`, no explicit versioning of the command protocol itself (if `params` shape for an action changes later, nothing signals "this is v2 of the protocol").

**Missing tests:** There are zero test files in the repo. Given the safety-critical nature of `safe_path()` specifically, this is the single highest-value place to start (see Roadmap).

**Missing Windows automation features** (genuinely absent, not necessarily needed): clipboard read/write, screenshot capture, window enumeration/focus (as opposed to just process list/kill), keyboard shortcuts (as opposed to only literal text typing), drag-and-drop, scroll actions.

**Missing file-system protections:** no file-size limits on `file_create`, no check preventing overwrite of an existing file without an explicit `overwrite: true` flag, no protection against path length / reserved-name issues specific to Windows (`CON`, `PRN`, `NUL`, etc. as filenames).

**Missing WebSocket events:** no server-initiated push (e.g., a process-exit notification, a file-change notification) — the current `/ws` is purely request/response, just HTTP-over-a-different-transport rather than using what WebSockets are actually good for.

**Missing process monitoring:** `list_processes` is a one-shot snapshot; no subscription to process start/stop events, no resource-usage figures (CPU/memory per process) despite `psutil` already being a dependency and trivially able to provide them.

**Missing plugin architecture:** discussed in Section 3 — not urgent yet.

**Missing CLI tool:** there's no command-line client bundled (only the PowerShell one-off `cronos.ps1` and the browser test console) — a small `cli.py` (`python cli.py move_mouse --x 500 --y 300`) would be a low-effort, high-value addition for scripting/testing without opening a browser.

**Missing GUI wrapper:** no system-tray icon / desktop indicator that the gateway is running, no visible way to see gateway status without hitting `/health` manually. For something that types and clicks on your behalf, a persistent visual "I am currently live and listening" indicator is a meaningful safety/trust feature, not just polish.

**Missing integration with AetherOS:** no reference to AetherOS anywhere in this repository's code, README, or either analysis doc — there is currently no integration surface between this project and an AetherOS project, planned or otherwise, that this audit could find in the repo itself.

---

## 5. Performance Review

At the current scope (single local user, human-speed commands), performance is not a real concern — every action is fast relative to human perception, and the codebase does nothing wasteful. That said, specific to a future higher-throughput or chat-driven use case:

- **`list_processes` iterates every running process on every call** (`psutil.process_iter`) with no caching and no filtering — fine occasionally, wasteful if an AI polls it frequently (e.g., "is the app still open?" checked in a loop).
- **`execute_command` runs synchronously inside an `async def` FastAPI handler.** None of `pyautogui`'s or `psutil`'s calls are async-aware, so each command blocks FastAPI's single event loop for its duration. For fast actions (mouse/keyboard) this is invisible; for anything that could hang (see Section 2's timeout point) it stalls every other concurrent request, including `/health`.
- **`load_config()` is cached in a module-level global** and never invalidated — a real correctness/performance tradeoff: fast (no repeated disk reads), but changing `config.json` (e.g., rotating the secret) requires a full process restart, which the in-repo analysis doc also flags as a missing hot-reload feature.
- **No batching.** Every command is one full request/response round trip, including auth + validation overhead, even for something like "type these 3 things and click twice" that a chat-driven AI would naturally want to send as one turn.
- No inefficient loops or obviously slow constructs found elsewhere in the codebase — it's small enough that this isn't a meaningful risk area yet.

---

## 6. Security Review

This is the most important section given what the tool does (keyboard/mouse/process/file control). Ordered by severity, based on the actual repository content, not hypotheticals:

**1. CRITICAL — Secrets and personal paths committed to a public repo (confirmed, not hypothetical).**
`config.json` is tracked in git with `"shared_secret": "CHANGE_ME_SECRET"` (the unmodified placeholder) and real Windows account paths (`C:/Users/Alex Kitipov/...`). `cronos.ps1` hardcodes the same placeholder token and a real local path. `logs/agent.log` is also tracked and contains real command history plus a real folder name inside a traceback. **None of this is a design flaw in the code — it's operational: these files should never have been committed, and the placeholder secret in particular means anyone who reads the public repo has the exact token this specific deployment currently uses (if it hasn't been changed locally).** Immediate remediation: rotate the secret now (in the *local, untracked* copy), then remove `config.json`, `logs/`, and `__pycache__/` from git history (not just delete going forward — `git filter-repo` or BFG if the secret must be considered burned either way, which it should be), and add a `.gitignore`.

**2. HIGH — Unsafe file operations / path sanitization gap.** `safe_path()`'s core logic is sound but doesn't defend against a symlink or NTFS junction planted inside an allowed directory pointing outside it (Section 2, detail above). Low likelihood in a single-user localhost tool, but the fix (resolve + re-validate the *final* real path, and optionally refuse to follow symlinks in file ops at all) is cheap relative to the blast radius if it's ever hit.

**3. HIGH — No rate limiting.** Confirmed absent — nothing in `server.py` limits request frequency. A malfunctioning or malicious caller with a valid token can hammer the endpoint indefinitely (self-inflicted DoS at minimum, e.g., filling the disk via repeated `file_create`, or making the mouse unusable via a `move_mouse` loop).

**4. MEDIUM — No command whitelisting per token / no permission model.** Confirmed — one token grants every action, unconditionally. There's no way today to hand out a scoped token (e.g., "can read files, cannot delete or launch processes") to a lower-trust caller.

**5. MEDIUM — No token expiration.** Confirmed — `shared_secret` is a single static string with no TTL and no rotation mechanism beyond manually editing `config.json` and restarting.

**6. MEDIUM — `open_app`'s `shell=True` widens "launch a named program" into "run a shell command line"** for any caller who already holds a valid token (Section 2, detail above). Since that caller is already fully trusted, this isn't a new authorization bypass — but it's a bigger blast radius than the action name implies, worth tightening if the token is ever shared more broadly.

**7. LOW — Token comparison isn't constant-time** (`==` instead of `hmac.compare_digest`). Low practical risk on localhost, free to fix.

**8. LOW — Logging doesn't redact potentially sensitive command content.** Confirmed — full `params` dicts are logged verbatim at INFO level.

**9. Not currently an issue, flag for the future:** CORS is wide open, justified today by the localhost-only bind. This is fine *as long as* nobody changes the bind address without also revisiting CORS — worth a code comment plus a startup assertion that refuses to boot if `host != "127.0.0.1"` and CORS is still `"*"`, so the two can't silently drift apart.

**Remote-execution risk assessment:** There is no remote-execution risk *from the network* today, because the bind is hardcoded to `127.0.0.1` and there's no tunneling/port-forwarding code in the repo. The realistic risk surface is entirely local: anything else running as the same Windows user (any other locally-running process, any browser tab if CORS/bind assumptions ever get relaxed) that can reach `127.0.0.1:8765` and knows or guesses the token gets full mouse/keyboard/process/file control. That's an accurate description of what this tool is *for*, so the mitigation is keeping the token secret and the bind localhost-only — both of which the code does correctly; the actual failure here (Finding 1) is operational, not architectural.

---

## 7. Modernization Roadmap

**Phase 0 — Hygiene (do first, before anything else, ~1 day):**
- Rotate the shared secret locally; scrub `config.json`, `logs/`, `__pycache__/` from git history; add `.gitignore` (`__pycache__/`, `*.pyc`, `logs/`, and either remove `config.json` from tracking or replace it with a checked-in `config.example.json` + a gitignored real `config.json`).
- Remove personal paths from any file that stays tracked (use `C:/Users/<you>/...` placeholders in docs/examples).
- Add `requirements.txt` (or `pyproject.toml`) pinning `fastapi`, `uvicorn[standard]`, `pyautogui`, `psutil`.

**Phase 1 — Safety hardening (~3-5 days):**
- Harden `safe_path()` against symlink/junction escapes.
- Add per-action timeout wrapping in `system_agent.execute_command`.
- Add basic rate limiting (even a simple in-memory token-bucket per source is enough for a localhost tool — no need for Redis).
- Move `pyautogui`/keyboard-mouse execution off the FastAPI event loop (run in a thread pool executor) so one slow action can't stall `/health` and other requests.
- Switch token comparison to `hmac.compare_digest`.

**Phase 2 — Protocol maturity (~1 week):**
- Add `GET /actions` introspection endpoint (name, required params, whether destructive/sandboxed) generated from the same registry that drives dispatch — solves the "AI has to already know the schema" gap without needing NLU.
- Add structured error codes alongside the existing human-readable `details` string.
- Decide explicitly whether natural-language parsing belongs server-side (NLU) or stays the calling AI's job, and document that decision — this single choice determines whether Phase 3 below is needed at all.

**Phase 3 — Chat integration (only if server-side NLU is the chosen path, ~2-3 weeks, roughly matching the plan already sketched in `Browser-Based AI Chat Integration.md`):**
- Chat-shaped frontend (message history, user/AI/system distinction) alongside — not necessarily replacing — the existing JSON test console.
- `/ws-chat` endpoint and a message-history/session layer.
- Natural-language → command parsing, starting rule-based/regex (as the existing doc proposes) before reaching for a model-based approach.

**Phase 4 — Access control maturity (as-needed, not urgent for single-user use):**
- Per-token scopes/permissions.
- Token expiration/rotation support.
- Structured audit log (separate from the debug log) recording caller identity, action, params (redacted), and result.

**Recommended libraries:** `pydantic` (FastAPI already depends on it — use it explicitly for the command schema instead of hand-rolled dict validation in `protocol.py`, which would also give you free OpenAPI docs at `/docs`); `python-dotenv` or plain environment variables for the secret specifically, so it never has to live in `config.json` at all; `slowapi` or a hand-rolled token-bucket for rate limiting (slowapi is the lighter lift); `pytest` + `pytest-asyncio` + `httpx` for testing FastAPI endpoints; `watchdog` only if config hot-reload becomes a real requirement.

**Test coverage plan (prioritized):**
1. `safe_path()` — the single highest-value target: inside-allowed-dir, outside-allowed-dir, empty-allowed-dirs (fail closed), symlink-escape attempt, relative-path traversal (`../../`) attempt.
2. `validate_token` / `validate_command` — missing token, wrong token, missing action, unknown action, missing required params.
3. Each `actions.py` function's error path (e.g., `file_delete` on a nonexistent path, `close_app` with no match) — these are cheap to test and currently entirely unverified.
4. One end-to-end test per HTTP/WS endpoint using `httpx`/`websockets` against a running test instance with a throwaway `config.json`.

**Documentation plan:** expand README's security section with the symlink caveat and the `open_app`/`close_app` sandbox exception explicitly; add a `SECURITY.md` describing the trust model in one place (who can do what if they have the token, what's sandboxed vs. not); add a `CONTRIBUTING.md` if this is meant to take outside PRs; add a `docs/PROTOCOL.md` documenting the JSON schema and any future versioning of it once Phase 2/3 land.

---

## 8. Actionable TODO List

**High priority**
- [ ] Rotate `shared_secret` in your local (untracked) config right now; treat the committed value as burned.
- [ ] Remove `config.json`, `logs/`, `agent/__pycache__/`, `gateway/__pycache__/` from git tracking; add `.gitignore`.
- [ ] Scrub real personal directory paths from `config.json`, `cronos.ps1`, and any committed docs; replace with placeholders.
- [ ] Add `requirements.txt` with pinned versions.
- [ ] Harden `safe_path()` against symlink/junction escapes.
- [ ] Add a per-action execution timeout.

**Medium priority**
- [ ] Add basic rate limiting on `/command` and `/ws`.
- [ ] Run blocking action calls (`pyautogui`, `psutil`, file I/O) in a thread pool instead of directly inside the async handler.
- [ ] Add `GET /actions` introspection endpoint.
- [ ] Switch token comparison to `hmac.compare_digest`.
- [ ] Add a confirmation/second-check path for destructive actions (`file_delete`, `close_app` on a multi-match).
- [ ] Add structured error codes to responses, not just free-text `details`.
- [ ] Write tests for `safe_path()` and `protocol.py` validation (see Section 7's test plan) — currently zero test coverage exists.
- [ ] Redact or omit sensitive-looking values from logged `params`.

**Low priority**
- [ ] Add a small CLI client (`cli.py`) for scripting without the browser console.
- [ ] Add a system-tray/visible "gateway is running" indicator.
- [ ] Add per-token scopes and token expiration.
- [ ] Add a structured audit log separate from the debug log.
- [ ] Decide and document the NLU-vs-AI-formats-JSON question from Phase 2, then build the chosen path.
- [ ] Add batching support for multi-step commands in a single request.
- [ ] Add missing automation primitives if genuinely needed: clipboard, screenshot, window focus, scroll.

---

## 9. Proposed Pull Requests

*(Descriptions only, as requested — no code included.)*

**PR 1 — "Stop tracking secrets, logs, and personal paths in git"**
- Description: Remove `config.json`, `logs/`, and both `__pycache__/` directories from version control; add `.gitignore`; add `config.example.json` with placeholder values as the new committed template.
- Files to modify: `.gitignore` (new), `config.example.json` (new), remove `config.json`/`logs/agent.log`/`agent/__pycache__/*`/`gateway/__pycache__/*` from tracking, update `README.md`'s setup instructions to reference copying the example file.
- Expected outcome: no secrets or personal information in the repo going forward.
- Risk level: Low (process change, no runtime behavior change) — but note the already-committed secret should be treated as permanently exposed regardless of this PR; history scrubbing is a separate, optional follow-up.
- Testing notes: verify the app still boots from a freshly copied `config.example.json → config.json`.

**PR 2 — "Harden safe_path against symlink/junction escape"**
- Description: After resolving the target path, additionally verify no path component between the allowed directory and the target is a symlink/junction pointing outside the sandbox; reject if so.
- Files to modify: `agent/utils.py` (`safe_path`), add corresponding tests.
- Expected outcome: file operations can no longer escape `allowed_directories` via a planted symlink.
- Risk level: Low-medium (touches the core safety function — needs solid test coverage before merge, not just visual review).
- Testing notes: unit tests for legitimate nested paths (should still pass), for an out-of-sandbox symlink target (should now be rejected), and for the existing traversal cases (should still be rejected).

**PR 3 — "Move blocking action execution off the event loop + add per-action timeout"**
- Description: Wrap `execute_command`'s dispatch in `run_in_executor` (or similar) so `pyautogui`/`psutil`/file-I/O calls don't block FastAPI's event loop; add a configurable per-action timeout that returns a structured timeout error instead of hanging indefinitely.
- Files to modify: `gateway/server.py`, `agent/system_agent.py`, `config.json` schema (new `action_timeout_seconds` field).
- Expected outcome: one slow/hung action no longer stalls concurrent requests (including `/health`); long-hanging actions fail cleanly instead of hanging forever.
- Risk level: Medium (changes execution model — needs testing under concurrent load, not just single-request testing).
- Testing notes: fire two concurrent requests where one is artificially slowed, confirm the other still responds promptly; confirm a deliberately-hung action times out and returns a clean error rather than hanging the connection.

**PR 4 — "Add GET /actions introspection endpoint"**
- Description: Expose the existing `ACTION_MAP` (name, required params, and new `destructive`/`sandboxed` flags) as a read-only JSON endpoint so any caller — human or AI — can discover the protocol without reading source.
- Files to modify: `agent/system_agent.py` (add metadata to `ACTION_MAP` entries), `gateway/server.py` (new endpoint).
- Expected outcome: self-describing API; directly unblocks an external AI that doesn't already know the exact schema.
- Risk level: Low (additive, read-only endpoint).
- Testing notes: verify the endpoint's output stays in sync with `ACTION_MAP` by generating it programmatically rather than hand-maintaining a duplicate list.

**PR 5 — "Basic rate limiting on /command and /ws"**
- Description: Add a simple in-memory token-bucket (or `slowapi`) limiter per token, configurable in `config.json`, to bound request frequency.
- Files to modify: `gateway/server.py`, `config.json` schema (new `rate_limit` fields), `requirements.txt`.
- Expected outcome: a runaway caller (buggy script, looping AI) can no longer flood the machine with actions.
- Risk level: Low-medium (could reject legitimate bursts if limits are set too tight — needs a sensible default and to be documented as configurable).
- Testing notes: verify normal single-command usage is unaffected; verify a rapid-fire burst past the configured limit gets a clean 429-style rejection, not a crash.

**PR 6 — "Introduce pydantic models for the command schema"**
- Description: Replace the hand-rolled dict validation in `gateway/protocol.py` with `pydantic` models (which FastAPI already depends on), gaining automatic `/docs` OpenAPI documentation as a side effect.
- Files to modify: `gateway/protocol.py`, `gateway/server.py`.
- Expected outcome: stronger validation guarantees, auto-generated API docs, less hand-written validation code to maintain.
- Risk level: Low-medium (refactor of a load-bearing validation path — needs the Section 7 test suite in place first so the refactor can be verified against known-good/known-bad cases).
- Testing notes: run the full validation test suite (missing action, missing params, wrong types, unknown action) before and after, confirm identical accept/reject behavior.

---

## 10. Summary

The core agent/gateway is small, well-organized, and gets the fundamentals right: fail-closed auth, localhost-only binding, and a centralized file sandbox. The two most important things to act on aren't architectural — they're that **a placeholder secret and real personal paths are currently committed to a public repository** (fix immediately, treat the secret as burned), and that **the project has zero test coverage** despite touching mouse/keyboard/file/process control, where a regression in `safe_path()` specifically would be a real security incident, not just a bug. Once those two are addressed, the roadmap above (timeout/concurrency hardening → protocol introspection → the chat-integration layer already scoped in the repo's own planning docs) is a reasonable, low-drama path from "solid personal tool" to the browser-chat-driven system the project is aiming for.
