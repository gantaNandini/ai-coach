Write-Host "Waiting for Ollama container to start..."
$maxWait = 120  # max 2 hours
$waited = 0

while ($waited -lt $maxWait) {
    Start-Sleep -Seconds 60
    $waited++

    $status = docker ps --filter "name=ai-coach-ollama-1" --format "{{.Status}}" 2>&1
    Write-Host "[$($waited)m] Ollama status: $status"

    if ($status -like "Up*") {
        Write-Host "Ollama is UP. Waiting 10s for API to be ready..."
        Start-Sleep -Seconds 10

        # Test if API responds
        try {
            $r = Invoke-WebRequest -Uri "http://localhost:11434/api/version" -UseBasicParsing -TimeoutSec 5
            Write-Host "Ollama API ready. Pulling gemma2:2b..."
            docker exec ai-coach-ollama-1 ollama pull gemma2:2b
            Write-Host "Model pull complete!"
            Write-Host "Restarting backend and worker to pick up Ollama..."
            docker restart ai-coach-backend-1 ai-coach-worker-1
            Start-Sleep -Seconds 10
            Write-Host "Running final health check..."
            $tk = (Invoke-WebRequest -Uri "http://localhost:8000/api/v1/auth/login" -Method POST -Body '{"email":"testadmin@aicoach.io","password":"Test1234!"}' -ContentType "application/json" -UseBasicParsing -TimeoutSec 15 | Select-Object -Expand Content | ConvertFrom-Json).access_token
            $h = @{Authorization="Bearer $tk"}
            $health = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/monitoring/health" -Headers $h -UseBasicParsing -TimeoutSec 10 | Select-Object -Expand Content | ConvertFrom-Json
            Write-Host "Health: ai_enabled=$($health.ai_enabled) llm_provider=$($health.llm_provider)"
            Write-Host "ollama=$($health.components.ollama)"
            break
        } catch {
            Write-Host "Ollama API not ready yet, waiting..."
        }
    }
}
