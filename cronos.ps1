$token = "CHANGE_ME_SECRET"
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

Add-Content -Path "C:\Users\Alex Kitipov\Downloads\ai_agent\cronos_log.txt" -Value $response