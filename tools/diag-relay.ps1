# Diagnose Windows -> WSL localhost relay for live_server.py (ASCII only)
param([int]$Port = 47822, [int]$Seconds = 75, [string]$Log)
$py = Join-Path $PSScriptRoot '..\widget\.venv\Scripts\python.exe'
"=== relay diagnosis port $Port $(Get-Date -Format 'HH:mm:ss.fff')" | Out-File $Log -Encoding utf8
$sv = Start-Process wsl.exe -ArgumentList '-d','Ubuntu-24.04','-u','root','-e','/opt/parakeet/venv/bin/python','/opt/parakeet/scripts/live_server.py','--port',"$Port",'--idle-exit','0','--debug' -WindowStyle Hidden -PassThru -RedirectStandardError "$Log.server.txt" -RedirectStandardOutput "$Log.server-out.txt"
"server wsl.exe started $(Get-Date -Format 'HH:mm:ss.fff')" | Out-File $Log -Append -Encoding utf8
$cu = Start-Process wsl.exe -ArgumentList '-d','Ubuntu-24.04','-u','root','-e','bash','-c',"for i in `$(seq 1 $Seconds); do printf '%s ' `$(date +%T); curl -s -m 2 -o /dev/null -w '%{http_code} %{time_total}\n' http://127.0.0.1:$Port/health || echo fail; sleep 1; done > /tmp/curl-probe.txt 2>&1" -WindowStyle Hidden -PassThru
"curl loop started $(Get-Date -Format 'HH:mm:ss.fff')" | Out-File $Log -Append -Encoding utf8
$code = "import socket,time`nfor i in range($Seconds):`n    t=time.time()`n    try:`n        s=socket.create_connection(('127.0.0.1',$Port),timeout=2);s.sendall(b'GET /health HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n');d=s.recv(60);s.close();r=d[:15]`n    except Exception as e: r=type(e).__name__`n    print(time.strftime('%H:%M:%S'), r, round(time.time()-t,3), flush=True)`n    time.sleep(max(0,1-(time.time()-t)))"
& $py -c $code 2>&1 | Out-File $Log -Append -Encoding utf8
"--- curl inside WSL (WSL clock)" | Out-File $Log -Append -Encoding utf8
& wsl.exe -d Ubuntu-24.04 -u root -e cat /tmp/curl-probe.txt 2>&1 | Out-File $Log -Append -Encoding utf8
"--- netstat" | Out-File $Log -Append -Encoding utf8
netstat -ano | Select-String ":$Port" | Out-File $Log -Append -Encoding utf8
try { Invoke-RestMethod -Method Post "http://127.0.0.1:$Port/shutdown" -TimeoutSec 3 | Out-Null } catch {}
& wsl.exe -d Ubuntu-24.04 -u root -e pkill -f live_server.py
"done $(Get-Date -Format 'HH:mm:ss.fff')" | Out-File $Log -Append -Encoding utf8
