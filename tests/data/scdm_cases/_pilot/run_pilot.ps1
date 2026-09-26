# Phase-A pilot: one headless launch over _pilot\pilot_cases.txt, then a GUI retry of headless failures.
& 'D:\training\caedecoder\scdm_cases\_framework\run_batch.ps1' -BatchName pilot `
  -CaseList 'D:\training\caedecoder\scdm_cases\_pilot\pilot_cases.txt' `
  -ResultDir 'D:\training\caedecoder\scdm_cases\_pilot' `
  -Manifest 'D:\training\caedecoder\scdm_cases\_pilot\pilot_manifest.json' -Phase pilot `
  -TimeoutSec 2400 -StallSec 600 -GuiRetryFailed
