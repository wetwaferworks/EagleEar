# Simulated-login test for Eagle Ear: runs ONLY the marked block from start-login.ps1,
# then drives the running instance through its IPC commands. Writes a log; changes nothing else.
param([string]$Log)
$ErrorActionPreference = 'Continue'
$W = (Resolve-Path (Join-Path $PSScriptRoot '..\widget')).Path
$DataLogs = 'R:\data\EagleEar\logs'
$py = Join-Path $W '.venv\Scripts\python.exe'
$app = Join-Path $W 'eagle_ear.pyw'
$stateFile = Join-Path $DataLogs 'state.json'
function L([string]$m) { $line = (Get-Date -Format 'HH:mm:ss.fff') + '  ' + $m; Add-Content -Path $Log -Value $line -Encoding ascii; Write-Output $line }
function Vram { (nvidia-smi --query-gpu=memory.used --format=csv,noheader).Trim() }
function Srv { $r = wsl -d Ubuntu-24.04 -e pgrep -f live_server.py; if ($r) { 'RUNNING pid ' + ($r -join ',') } else { 'none' } }
function Procs { @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*eagle_ear.pyw*' -and $_.Name -like 'python*' }) }
function Cmd([string]$c) { & $py $app --cmd $c; Start-Sleep -Milliseconds 900 }
function State { Cmd 'dump'; try { Get-Content $stateFile -Raw | ConvertFrom-Json } catch { $null } }
function ShowState([string]$tag) {
    $s = State
    if ($s) { L ("{0}: engine={1} visible={2} recording={3} tray_added={4} toolwindow={5} appwindow={6} server_alive={7} idle_min={8} vram={9} wsl_server={10} widget_pids={11}" -f $tag, $s.engine, $s.visible, $s.recording, $s.tray_added, $s.toolwindow, $s.appwindow, $s.server_alive, $s.idle_unload_min, (Vram), (Srv), ((Procs).ProcessId -join ',')) }
    else { L "${tag}: no state" }
    return $s
}
function WaitEngine([string]$want, [int]$sec) {
    $t0 = Get-Date
    while (((Get-Date) - $t0).TotalSeconds -lt $sec) {
        Cmd 'dump'
        try { $s = Get-Content $stateFile -Raw | ConvertFrom-Json; if ($s.engine -eq $want) { return [math]::Round(((Get-Date) - $t0).TotalSeconds, 1) } } catch {}
        Start-Sleep 2
    }
    return -1
}

L "==== 38 simulated-login test"
L ("baseline: vram=" + (Vram) + " wsl_server=" + (Srv) + " widget_pids=[" + ((Procs).ProcessId -join ',') + "]")

# 1) run just the Parakeet block from the real login script
$src = Get-Content "$env:LOCALAPPDATA\CortanaShield\start-login.ps1" -Raw
$m = [regex]::Match($src, '(?s)# >>> Parakeet Live.*?# <<< Parakeet Live')
if (-not $m.Success) { L 'FAIL: marker block not found'; exit 1 }
$script:loginLog = @()
function Write-Login([string]$msg) { $script:loginLog += $msg }
L "running the extracted login block (Write-Login stubbed, health.log untouched)"
Invoke-Expression $m.Value
L ("Write-Login said: " + ($script:loginLog -join ' | '))
Start-Sleep 6
$wpids = (Procs).ProcessId
L ("widget processes after login block: [" + ($wpids -join ',') + "]")
$kids = @(Get-CimInstance Win32_Process | Where-Object { $wpids -contains $_.ParentProcessId } | ForEach-Object { $_.Name + ':' + $_.ProcessId })
L ("child processes of the widget (expect none: no wsl.exe): [" + ($kids -join ',') + "]")
$s = ShowState 'after login'
$ok1 = ($s.engine -eq 'unloaded') -and (-not $s.visible) -and $s.tray_added -and (-not $s.server_alive)
L ("CHECK tray-only at login, model not loaded: " + $ok1)

# 2) second launch (what the Start Menu shortcut does) -> must show + load in the SAME instance
L "second launch (no args) -> should focus/show existing instance and start loading"
$t0 = Get-Date
& $py $app
L ("second launch returned after " + [math]::Round(((Get-Date) - $t0).TotalSeconds, 1) + " s")
$s = ShowState 'after second launch'
L ("CHECK single instance: " + (@(Procs).Count -eq 1) + "  shown: " + $s.visible + "  engine: " + $s.engine)
$rs = WaitEngine 'ready' 150
L ("engine ready after +" + $rs + " s")
$s = ShowState 'ready'

# 3) a third launch while loaded must not start a second server
& $py $app
Start-Sleep 2
L ("third launch: widget_pids=[" + ((Procs).ProcessId -join ',') + "] wsl_server=" + (Srv))

# 4) hide / show / unload
Cmd 'hide'; $s = ShowState 'after --cmd hide'
L ("CHECK hidden and still loaded: " + ((-not $s.visible) -and $s.engine -eq 'ready'))
Cmd 'toggle'; $s = ShowState 'after --cmd toggle (show)'
L ("CHECK shown + toolwindow: " + ($s.visible -and $s.toolwindow -and -not $s.appwindow))
Cmd 'unload'
$ru = WaitEngine 'unloaded' 30
Start-Sleep 2
$s = ShowState ("after --cmd unload (+" + $ru + " s)")
L ("CHECK unload frees VRAM: engine=" + $s.engine + " vram=" + (Vram) + " wsl_server=" + (Srv))
Cmd 'quit'; Start-Sleep 4
L ("after --cmd quit: widget_pids=[" + ((Procs).ProcessId -join ',') + "] vram=" + (Vram) + " wsl_server=" + (Srv))

# 5) idle auto-unload (0.5 min), and Record as the first action (loads the model)
$td = Join-Path $env:TEMP 'eagle-login-sim-training-data'
L "start --tray --idle-min 0.5 (test-only training dir), then --cmd record as first action"
Start-Process -FilePath (Join-Path $W '.venv\Scripts\pythonw.exe') -ArgumentList @('"' + $app + '"', '--tray', '--no-save', '--idle-min', '0.5', '--training-dir', '"' + $td + '"') -WorkingDirectory $W
Start-Sleep 5
$s = ShowState 'idle-test instance'
Cmd 'record'
$s = ShowState 'after --cmd record'
$rr = WaitEngine 'ready' 150
$s = ShowState ("ready after record (+" + $rr + " s)")
Start-Sleep 3
Cmd 'record'
$s = ShowState 'after second --cmd record (stop)'
$t1 = Get-Date
$ri = WaitEngine 'unloaded' 120
$s = ShowState ("idle auto-unload after +" + $ri + " s of waiting")
L ("CHECK idle auto-unload: engine=" + $s.engine + " vram=" + (Vram) + " wsl_server=" + (Srv))
Cmd 'quit'; Start-Sleep 4
L ("final: widget_pids=[" + ((Procs).ProcessId -join ',') + "] vram=" + (Vram) + " wsl_server=" + (Srv) + " port51761=[" + ((Get-NetTCPConnection -LocalPort 51761 -State Listen -ErrorAction SilentlyContinue).OwningProcess -join ',') + "]")
L "---- widget.log tail"
Get-Content (Join-Path $DataLogs 'widget.log') -Tail 30 | ForEach-Object { Add-Content -Path $Log -Value ('    ' + $_) -Encoding ascii }
L "==== done"
