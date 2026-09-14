# Environment check of the Prime Flight workspace. Changes nothing, only reports.
# Run:  powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$repos = Join-Path $root "external"
$stand = "G:\gat-streaming"

function Check($label, $ok, $hint) {
  $mark = if ($ok) { "[OK] " } else { "[--] " }
  Write-Host ($mark + $label)
  if (-not $ok -and $hint) { Write-Host ("       -> " + $hint) }
}

Write-Host "== Prime Flight workspace: $root"
Check "CLAUDE.md" (Test-Path "$root\CLAUDE.md") ""
Check "tasks\BOARD.md" (Test-Path "$root\tasks\BOARD.md") ""
foreach ($d in @("tasks\notes", "tasks\status", "docs\inbox", "docs\decisions")) {
  if (-not (Test-Path "$root\$d")) { New-Item -ItemType Directory -Force "$root\$d" | Out-Null }
}

Write-Host "`n== Repository clones ($repos)"
Check "external\ (read-only GitLab clones) exists" (Test-Path $repos) "git clone https://gitlab.com/dxgat/detectors/<repo>.git external\<repo>"
foreach ($r in @("general_model", "cv_trackers", "cv_common", "db_worker", "camera_software")) {
  $p = Join-Path $repos $r
  $ok = Test-Path (Join-Path $p ".git")
  $info = ""
  if ($ok) {
    $br = (git -C $p branch --show-current 2>$null)
    $sha = (git -C $p rev-parse --short HEAD 2>$null)
    $info = " [$br @ $sha]"
  }
  Check ("$r" + $info) $ok ("git clone https://gitlab.com/dxgat/" + $(if ($r -eq "general_model" -or $r -eq "camera_software") { "detectors" } else { "utils" }) + "/$r.git $p")
}
$mods = Get-ChildItem $repos -Directory -ErrorAction SilentlyContinue | Where-Object { Test-Path (Join-Path $_.FullName "main.py") }
Write-Host ("   modules with main.py: " + $mods.Count)

Write-Host "`n== Streaming stand (test bench) ($stand)"
Check "G:\gat-streaming exists" (Test-Path $stand) ""
Check "streaming\contract.py" (Test-Path "$stand\streaming\contract.py") ""
Check "tools\compare_runs.py" (Test-Path "$stand\tools\compare_runs.py") ""
Check "data\ (inferences/gt for level 2)" (Test-Path "$stand\data") "needs inferences from cv-modules-topics + gt_by_video.json"

Write-Host "`n== Python"
$py = (Get-Command python -ErrorAction SilentlyContinue)
Check "python in PATH" ($null -ne $py) ""
if ($py) {
  foreach ($pkg in @("openpyxl", "pytest")) {
    $r = python -c "import $pkg" 2>$null; Check "pip: $pkg" ($LASTEXITCODE -eq 0) "pip install $pkg"
  }
}

Write-Host "`n== Git access (without password prompts)"
$env:GIT_TERMINAL_PROMPT = "0"
foreach ($u in @("https://gitlab.com/dxgat/detectors/general_model.git", "https://gitlab.com/dxgat/utils/db_worker.git")) {
  $out = git ls-remote --heads $u 2>&1 | Select-Object -First 1
  Check $u ($out -match "refs/heads") "check the GitLab credentials (Git Credential Manager)"
}

Write-Host "`nDone. Next: cd $root; claude"
