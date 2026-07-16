// frontend/app.js
// Plain JS, no frameworks. Sends the textarea's JSON to the gateway's
// POST /command endpoint and prints the response in the log area.

const sendBtn = document.getElementById("sendBtn");
const logEl = document.getElementById("log");
const commandInput = document.getElementById("commandInput");
const gatewayUrlInput = document.getElementById("gatewayUrl");
const tokenInput = document.getElementById("tokenInput");

function logLine(text, cls) {
  const line = document.createElement("div");
  if (cls) line.className = cls;
  const timestamp = new Date().toLocaleTimeString();
  line.textContent = `[${timestamp}] ${text}`;
  logEl.appendChild(line);
  logEl.scrollTop = logEl.scrollHeight;
}

async function sendCommand() {
  let payload;
  try {
    payload = JSON.parse(commandInput.value);
  } catch (e) {
    logLine(`Invalid JSON in textarea: ${e.message}`, "err");
    return;
  }

  const url = gatewayUrlInput.value.trim();
  const token = tokenInput.value.trim();

  logLine(`Sending: ${JSON.stringify(payload)}`);

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Auth-Token": token,
      },
      body: JSON.stringify(payload),
    });

    const data = await response.json();
    const cls = response.ok && data.status === "ok" ? "ok" : "err";
    logLine(`Response (${response.status}): ${JSON.stringify(data)}`, cls);
  } catch (e) {
    logLine(`Request failed: ${e.message}`, "err");
  }
}

sendBtn.addEventListener("click", sendCommand);
