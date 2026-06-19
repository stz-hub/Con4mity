<#
.SYNOPSIS
    Injecte de faux logs "Failed password" dans OpenSearch local pour tester
    les règles de détection (ex: SSH Brute Force, seuil = 10 en 1 minute).

.EXAMPLE
    .\seed_logs.ps1
    .\seed_logs.ps1 -TargetHost "srv-web01" -Count 15
#>
param(
    [string]$TargetHost = "test-server",
    [int]$Count = 12
)

$uri = "http://localhost:9200/con4mity-logs-test/_doc"

for ($i = 1; $i -le $Count; $i++) {
    $ts = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    $port = Get-Random -Minimum 1024 -Maximum 65000
    $body = @{
        "@timestamp" = $ts
        host         = $TargetHost
        message      = "Failed password for invalid user admin from 203.0.113.7 port $port ssh2"
        severity     = "high"
        category     = "authentication"
    } | ConvertTo-Json -Compress

    Invoke-RestMethod -Uri $uri -Method Post -ContentType "application/json; charset=utf-8" -Body $body | Out-Null
}

Write-Host "$Count logs 'Failed password' injectes dans con4mity-logs-test (host=$TargetHost)"
Write-Host "Attends jusqu'a 30s, puis verifie : docker compose logs -f elastalert"
