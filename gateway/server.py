"""
gateway/server.py

FastAPI gateway that an external AI (or the test frontend) talks to.

Security posture:
- Binds ONLY to 127.0.0.1 -- never reachable from other machines on the
  network, even if a firewall rule is misconfigured.
- Every /command and /ws message must include the shared_secret from
  config.json, either as an "X-Auth-Token" header or a "token" field in
  the JSON body. Requests without a valid token are rejected (401).
- Commands are schema-validated (protocol.py) before they ever reach
  agent/system_agent.py.

Run from the ai_agent/ project root with:
    python -m uvicorn gateway.server:app --host 127.0.0.1 --port 8765
(run_all.bat does this for you)
"""

import json

from fastapi import FastAPI, Request, Header, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from agent.system_agent import execute_command
from agent.utils import load_config, get_logger, error_result
from gateway.protocol import validate_command, validate_token

logger = get_logger("ai_agent.gateway")
config = load_config()

app = FastAPI(title="AI System Agent Gateway", version="1.0.0")

# CORS is left open so the plain-HTML test frontend (opened as a local
# file:// page) can call the API. This is safe here because the server
# itself never listens on anything but 127.0.0.1.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/command")
async def command_endpoint(request: Request, x_auth_token: str = Header(default=None)):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content=error_result("Invalid JSON body"))

    if not validate_token(body, header_token=x_auth_token):
        logger.warning("Rejected unauthorized /command request")
        return JSONResponse(status_code=401, content=error_result("Invalid or missing token"))

    valid, err = validate_command(body)
    if not valid:
        return JSONResponse(status_code=400, content=err)

    result = execute_command(body)
    return JSONResponse(content=result)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                body = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json(error_result("Invalid JSON"))
                continue

            # WebSocket clients must put the token inside the JSON body
            # itself, since there's no per-message header.
            if not validate_token(body):
                await websocket.send_json(error_result("Invalid or missing token"))
                continue

            valid, err = validate_command(body)
            if not valid:
                await websocket.send_json(err)
                continue

            result = execute_command(body)
            await websocket.send_json(result)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")


if __name__ == "__main__":
    import uvicorn
    port = config.get("gateway_port", 8765)
    # Bind ONLY to localhost -- never 0.0.0.0.
    uvicorn.run("gateway.server:app", host="127.0.0.1", port=port, reload=False)
