# Phase B batch launcher: runs the given batches sequentially via run_batch.ps1 (headless, no GUI retry).
param([string[]]$Batches, [string]$Suffix = "")
$root = "D:\training\caedecoder\scdm_cases"
foreach ($b in $Batches) {
    $name = $b + $Suffix
    $list = Join-Path $root ("_batches\" + $name + ".txt")
    if (-not (Test-Path $list)) { Write-Output "missing list $list"; continue }
    Write-Output ("=== {0} start {1}" -f $name, (Get-Date -Format "HH:mm:ss"))
    & (Join-Path $root "_framework\run_batch.ps1") -BatchName $name -CaseList $list -ResultDir (Join-Path $root "_batches") -Manifest (Join-Path $root "manifest.json") -Phase "phaseB"
    Write-Output ("=== {0} end {1}" -f $name, (Get-Date -Format "HH:mm:ss"))
}
