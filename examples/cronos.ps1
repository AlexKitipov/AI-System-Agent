# Example PowerShell client for sending one command to the local gateway.
# Copy this file before customizing it with local paths or tokens.

$token = "CHANGE_ME_TO_A_RANDOM_SECRET"
$body = @{
    action = "click"
    params = @{
        x = 500
        y = 300
    }
} | ConvertTo-Json

$response = Invoke-RestMethod -Uri "http://127.0.0.1:8765/command" `
    -Method POST `
    -Headers @{ "X-Auth-Token" = $token } `
    -Body $body `
    -ContentType "application/json"

$response | ConvertTo-Json -Depth 10
