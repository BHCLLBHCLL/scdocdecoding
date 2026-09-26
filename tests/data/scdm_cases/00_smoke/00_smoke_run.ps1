# Smoke runner: launches SpaceClaim V195 in batch against 00_smoke_box_001_20x20x20.py.
# Writes only inside D:\training\caedecoder\scdm_cases\00_smoke.
$ErrorActionPreference = 'Continue'
$exe    = 'C:\Program Files\ANSYS Inc\v195\SCDM\SpaceClaim.exe'
$d      = 'D:\training\caedecoder\scdm_cases\00_smoke'
$script = "$d\00_smoke_box_001_20x20x20.py"
$scdoc  = "$d\00_smoke_box_001_20x20x20.scdoc"
$res    = "$d\00_smoke_result.json"
$repo   = 'D:\training\caedecoder\scdocdecoding'
$utf8   = New-Object System.Text.UTF8Encoding($false)
Add-Type -AssemblyName System.IO.Compression.FileSystem

'== V19 scripting type names present'
Select-String -Path 'C:\Program Files\ANSYS Inc\v195\SCDM\Scripting\LoadSCDMAPITypesV19.py' -Pattern 'BlockBody|DocumentHelper|DocumentSave|SketchRectangle|ExtrudeFaces' |
  Select-Object -First 12 | ForEach-Object { '  ' + $_.Line.Trim() }

$pre = @(Get-Process SpaceClaim -ErrorAction SilentlyContinue)
if ($pre.Count) { 'ABORT: SpaceClaim already running, PIDs ' + ($pre.Id -join ','); exit 2 }

function Run-SC([string]$tag, [string]$extra) {
  Remove-Item $res, $scdoc -ErrorAction SilentlyContinue
  $argline = "/RunScript=`"$script`" /ExitAfterScript=True /Splash=False /Welcome=False $extra".Trim()
  Write-Host "== RUN [$tag]: `"$exe`" $argline"
  $start = Get-Date
  $sw = [Diagnostics.Stopwatch]::StartNew()
  $p = Start-Process -FilePath $exe -ArgumentList $argline -PassThru
  $titles = @{}; $sentAt = $null; $killed = $null
  while (-not $p.HasExited) {
    $t = $sw.Elapsed.TotalSeconds
    if ($t -gt 300) { $killed = 'timeout 300s'; break }
    if ($sentAt -and ($t - $sentAt) -gt 60) { $killed = 'did not exit 60s after sentinel'; break }
    try { $p.Refresh(); if ($p.MainWindowHandle -ne 0) { $titles['SC: ' + $p.MainWindowTitle] = 1 } } catch {}
    Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -match 'Licens|ANSYS|SpaceClaim' } |
      ForEach-Object { $titles[$_.ProcessName + ': ' + $_.MainWindowTitle] = 1 }
    if (-not $sentAt -and (Test-Path $res)) {
      $c = Get-Content $res -Raw -ErrorAction SilentlyContinue
      if ($c -match '"stage": "done"') { $sentAt = $t }
    }
    Start-Sleep -Milliseconds 1000
  }
  if ($killed) { try { $p.Kill() } catch {} }
  Start-Sleep -Seconds 2
  Get-Process SpaceClaim -ErrorAction SilentlyContinue | Where-Object { $_.StartTime -ge $start } |
    ForEach-Object { Write-Host "  killing leftover SpaceClaim PID $($_.Id)"; try { $_.Kill() } catch {} }
  $wall = [math]::Round($sw.Elapsed.TotalSeconds, 1)
  $exit = $null; try { $exit = $p.ExitCode } catch {}
  $sent = if (Test-Path $res) { Get-Content $res -Raw } else { $null }
  Write-Host "  wall_s=$wall exit=$exit killed=$killed sentinel_final_at_s=$sentAt"
  Write-Host ("  windows seen: " + (($titles.Keys | Sort-Object) -join ' | '))
  Write-Host ("  sentinel: " + $(if ($sent) { $sent } else { '<none>' }))
  if ($sent) { [IO.File]::WriteAllText("$d\00_smoke_result_$tag.json", $sent, $utf8) }
  $ok = $sent -and ($sent -match '"success": true') -and (Test-Path $scdoc)
  return [pscustomobject]@{ tag = $tag; cmd = "`"$exe`" $argline"; wall_s = $wall; exit = $exit; killed = $killed; ok = [bool]$ok; windows = @($titles.Keys) }
}

$runs = @()
$r1 = Run-SC 'headless' '/Headless=True'; $runs += $r1
if (-not $r1.ok) { $r2 = Run-SC 'gui' ''; $runs += $r2 }
$runs | ForEach-Object { "  RESULT $($_.tag): ok=$($_.ok) wall_s=$($_.wall_s)" }

'== VALIDATE'
$entries = @()
if (Test-Path $scdoc) {
  'size bytes: ' + (Get-Item $scdoc).Length
  try {
    $z = [IO.Compression.ZipFile]::OpenRead($scdoc)
    $entries = @($z.Entries | ForEach-Object { $_.FullName })
    $z.Entries | ForEach-Object { '  {0,8} {1}' -f $_.Length, $_.FullName }
    $z.Dispose()
    'valid zip: True; has SpaceClaim/document.xml: ' + ($entries -contains 'SpaceClaim/document.xml') +
      '; geometry-like parts: ' + (@($entries | Where-Object { $_ -match '\.sab$|[Gg]eometry' }) -join ', ')
  } catch { 'zip open FAILED: ' + $_ }
} else { 'scdoc MISSING' }

'== PARSER (read-only, -B, PYTHONPATH=repo, cwd=00_smoke)'
$parserOut = $null
if (Test-Path $scdoc) {
  $pyc = @("$env:USERPROFILE\.conda\envs\scdm\python.exe", 'C:\ProgramData\anaconda3\envs\scdm\python.exe', 'C:\ProgramData\anaconda3\python.exe') |
    Where-Object { Test-Path $_ } | Select-Object -First 1
  "python: $pyc"
  $env:PYTHONPATH = $repo; $env:PYTHONDONTWRITEBYTECODE = '1'
  Push-Location $d
  $parserOut = (& $pyc -B -m scdoc_parser $scdoc -o "$d\00_smoke_parser_report.json" 2>&1 | Out-String)
  "exit=$LASTEXITCODE"
  $parserOut
  Pop-Location
}

'== METADATA'
$meta = [ordered]@{
  case_id = '00_smoke_box_001_20x20x20'
  category = '00_smoke'
  feature = 'box (BlockBody / sketch rectangle + extrude fallback)'
  description = 'Smoke test: 20x20x20 mm solid block at origin, single body'
  params = [ordered]@{ length_mm = 20; width_mm = 20; height_mm = 20; corner1_mm = @(0, 0, 0); corner2_mm = @(20, 20, 20); extrude_type = 'ForceIndependent' }
  script_api = 'SpaceClaim V19 recording-style scripting (RunScript host namespace)'
  script_commands = @('DocumentHelper.CreateNewDocument', 'BlockBody.Create', 'SketchRectangle.Create+ExtrudeFaces.Execute (fallback)', 'DocumentSave.Execute', 'Document.SaveAs (fallback)')
  expected = [ordered]@{ bodies = 1; faces = 6; edges = 12; vertices = 8; volume_mm3 = 8000; surface_types = @('plane'); curve_types = @('straight') }
  files = [ordered]@{ script = '00_smoke_box_001_20x20x20.py'; scdoc = '00_smoke_box_001_20x20x20.scdoc'; result = '00_smoke_result.json' }
  spaceclaim = [ordered]@{ product = 'ANSYS SpaceClaim 2019 R3'; version = '2019.3.38912'; exe = $exe }
  runs = $runs
  working_command = (($runs | Where-Object ok | Select-Object -First 1).cmd)
  scdoc_entries = $entries
  generated_at = (Get-Date).ToString('yyyy-MM-ddTHH:mm:sszzz')
}
[IO.File]::WriteAllText("$d\00_smoke_box_001_20x20x20.json", ($meta | ConvertTo-Json -Depth 6), $utf8)
'metadata written'
'== FOLDER'
Get-ChildItem $d | ForEach-Object { '  {0,9} {1}' -f $_.Length, $_.Name }