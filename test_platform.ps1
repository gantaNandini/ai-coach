param()
$ErrorActionPreference = "Continue"
$base = "http://localhost:8000/api/v1"
$pass = 0
$fail = 0
$ts   = [System.DateTime]::Now.Ticks

# Login
try {
    $loginBody = '{"email":"testadmin@aicoach.io","password":"Test1234!"}'
    $lr = Invoke-WebRequest -Uri "$base/auth/login" -Method POST -Body $loginBody -ContentType "application/json" -UseBasicParsing -TimeoutSec 15
    $tk = ($lr.Content | ConvertFrom-Json).access_token
    $h  = @{ Authorization = "Bearer $tk" }
    Write-Host "LOGIN OK token=$($tk.Length)chars"
} catch {
    Write-Host "LOGIN FAILED - aborting"
    exit 1
}

function Chk {
    param($label, $url, $method = "GET", $body = $null, $expect = 200)
    try {
        $p = @{ Uri = $url; Method = $method; Headers = $h; UseBasicParsing = $true; TimeoutSec = 15 }
        if ($body) { $p.Body = $body; $p.ContentType = "application/json" }
        $r = Invoke-WebRequest @p
        if ($r.StatusCode -eq $expect) {
            $script:pass++
            Write-Host "PASS [$($r.StatusCode)] $label"
        } else {
            $script:fail++
            Write-Host "FAIL [$($r.StatusCode)] $label  (expected $expect)"
        }
    } catch {
        $code = $_.Exception.Response.StatusCode.value__
        if ($code -eq $expect) {
            $script:pass++
            Write-Host "PASS [$code] $label"
        } else {
            $script:fail++
            Write-Host "FAIL [$code] $label  (expected $expect)"
        }
    }
}

# ---------- AUTH ----------
Write-Host ""
Write-Host "=== AUTH ==="
Chk "GET /auth/me"                    "$base/auth/me"
Chk "POST /auth/refresh bad => 401"   "$base/auth/refresh" "POST" '{"refresh_token":"bad"}' 401

# ---------- USERS ----------
Write-Host ""
Write-Host "=== USERS ==="
Chk "GET /users/me"                   "$base/users/me"
Chk "PATCH /users/me"                 "$base/users/me" "PATCH" '{"full_name":"Admin User"}'

# ---------- MODULES ----------
Write-Host ""
Write-Host "=== MODULES ==="
Chk "GET /modules/"                   "$base/modules/"

$modKey  = "sbi_$ts"
$modBody = "{`"key`":`"$modKey`",`"name`":`"SBI Test $ts`",`"blurb`":`"test`"}"
$mid = $null
try {
    $mr  = Invoke-WebRequest -Uri "$base/modules/" -Method POST -Body $modBody -ContentType "application/json" -Headers $h -UseBasicParsing -TimeoutSec 15
    $mid = ($mr.Content | ConvertFrom-Json).id
    $script:pass++
    Write-Host "PASS [$($mr.StatusCode)] POST /modules/  id=$($mid.Substring(0,8))"
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    $script:fail++
    Write-Host "FAIL [$code] POST /modules/"
}

# ---------- SESSIONS ----------
Write-Host ""
Write-Host "=== SESSIONS ==="
Chk "GET /sessions/coaching"          "$base/sessions/coaching"
Chk "GET /sessions/roleplay"          "$base/sessions/roleplay"

# Use the seeded published SBI module
$pubMods   = Invoke-WebRequest -Uri "$base/modules/?status=published" -Headers $h -UseBasicParsing -TimeoutSec 15 | Select-Object -Expand Content | ConvertFrom-Json
$pubMid    = if ($pubMods.items.Count -gt 0) { $pubMods.items[0].id } else { $null }
$sid       = $null

if ($pubMid) {
    $sessBody = "{`"module_id`":`"$pubMid`"}"
    try {
        $sr  = Invoke-WebRequest -Uri "$base/sessions/coaching" -Method POST -Body $sessBody -ContentType "application/json" -Headers $h -UseBasicParsing -TimeoutSec 15
        $sid = ($sr.Content | ConvertFrom-Json).id
        $script:pass++
        Write-Host "PASS [$($sr.StatusCode)] POST /sessions/coaching  id=$($sid.Substring(0,8))"
    } catch {
        $code = $_.Exception.Response.StatusCode.value__
        $script:fail++
        # Capture body for diagnostics
        try {
            $stream = $_.Exception.Response.GetResponseStream()
            $reader = New-Object System.IO.StreamReader($stream)
            $errBody = $reader.ReadToEnd()
        } catch { $errBody = "(unreadable)" }
        Write-Host "FAIL [$code] POST /sessions/coaching  $errBody"
    }
} else {
    $script:fail++
    Write-Host "FAIL POST /sessions/coaching  (no published module found)"
}

if ($sid) {
    Chk "GET /sessions/coaching/{id}" "$base/sessions/coaching/$sid"
}

# ---------- KNOWLEDGE BASE ----------
Write-Host ""
Write-Host "=== KNOWLEDGE BASE ==="
Chk "GET /knowledge/"                 "$base/knowledge/"

# Delete old test KBs to stay under the plan limit
$existingKbs = Invoke-WebRequest -Uri "$base/knowledge/" -Headers $h -UseBasicParsing -TimeoutSec 15 | Select-Object -Expand Content | ConvertFrom-Json
foreach ($kb in $existingKbs.items) {
    if ($kb.name -like "TestKB_*") {
        try { Invoke-WebRequest -Uri "$base/knowledge/$($kb.id)" -Method DELETE -Headers $h -UseBasicParsing -TimeoutSec 10 | Out-Null } catch {}
    }
}

$kbName = "TestKB_$ts"
$kbBody = "{`"name`":`"$kbName`"}"
$kid    = $null
try {
    $kr  = Invoke-WebRequest -Uri "$base/knowledge/" -Method POST -Body $kbBody -ContentType "application/json" -Headers $h -UseBasicParsing -TimeoutSec 15
    $kid = ($kr.Content | ConvertFrom-Json).id
    $script:pass++
    Write-Host "PASS [$($kr.StatusCode)] POST /knowledge/  id=$($kid.Substring(0,8))"
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    try {
        $stream = $_.Exception.Response.GetResponseStream()
        $reader = New-Object System.IO.StreamReader($stream)
        $errBody = $reader.ReadToEnd()
    } catch { $errBody = "" }
    $script:fail++
    Write-Host "FAIL [$code] POST /knowledge/  $errBody"
}

if ($kid) {
    Chk "GET /knowledge/{id}"         "$base/knowledge/$kid"

    $srcBody = "{`"title`":`"SBI Guide`",`"content`":`"Situation Behaviour Impact is a structured feedback framework for coaching.`"}"
    $srcId   = $null
    try {
        $srcR  = Invoke-WebRequest -Uri "$base/knowledge/$kid/sources/text" -Method POST -Body $srcBody -ContentType "application/json" -Headers $h -UseBasicParsing -TimeoutSec 15
        $srcId = ($srcR.Content | ConvertFrom-Json).id
        $srcStatus = ($srcR.Content | ConvertFrom-Json).status
        $script:pass++
        Write-Host "PASS [$($srcR.StatusCode)] POST /knowledge/{id}/sources/text  status=$srcStatus"
    } catch {
        $code = $_.Exception.Response.StatusCode.value__
        $script:fail++
        Write-Host "FAIL [$code] POST /knowledge/{id}/sources/text"
    }

    if ($srcId) {
        Start-Sleep -Seconds 5
        Chk "GET source status (ingestion)" "$base/knowledge/$kid/sources/$srcId/status"
    }
}

# ---------- PROGRESS ----------
Write-Host ""
Write-Host "=== PROGRESS ==="
Chk "GET /progress/"                           "$base/progress/"
Chk "GET /progress/achievements"               "$base/progress/achievements"
Chk "GET /progress/achievements/mine"          "$base/progress/achievements/mine"
Chk "GET /progress/notifications/unread-count" "$base/progress/notifications/unread-count"

# ---------- BILLING ----------
Write-Host ""
Write-Host "=== BILLING ==="
Chk "GET /billing/plans"                       "$base/billing/plans"
Chk "GET /billing/subscription"                "$base/billing/subscription"

# ---------- ANALYTICS ----------
Write-Host ""
Write-Host "=== ANALYTICS ==="
Chk "GET /analytics/dashboard  (admin)"        "$base/analytics/dashboard"
Chk "GET /analytics/session-trend"             "$base/analytics/session-trend"
Chk "GET /analytics/module-performance"        "$base/analytics/module-performance"

# ---------- MONITORING ----------
Write-Host ""
Write-Host "=== MONITORING ==="
Chk "GET /monitoring/health"                   "$base/monitoring/health"
Chk "GET /monitoring/tasks"                    "$base/monitoring/tasks"
Chk "GET /monitoring/stats  (403 non-superadmin)"  "$base/monitoring/stats"  "GET" $null 403
Chk "GET /monitoring/config (403 non-superadmin)"  "$base/monitoring/config" "GET" $null 403

# ---------- FRONTEND ----------
Write-Host ""
Write-Host "=== FRONTEND ==="
try {
    $fr = Invoke-WebRequest -Uri "http://localhost:5173" -UseBasicParsing -TimeoutSec 10
    $script:pass++
    Write-Host "PASS [$($fr.StatusCode)] Frontend loads  ($($fr.Content.Length) bytes)"
} catch {
    $script:fail++
    Write-Host "FAIL Frontend  $($_.Exception.Message)"
}

# ---------- SUMMARY ----------
Write-Host ""
Write-Host "=============================="
Write-Host "TOTAL:  $pass PASSED  /  $fail FAILED"
Write-Host "=============================="
