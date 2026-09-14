# Перевірка оточення воркспейсу Prime Flight. Нічого не змінює, лише звітує.
# Запуск:  powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$repos = "G:\deepx_gat"
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

Write-Host "`n== Клони репозиторіїв ($repos)"
Check "G:\deepx_gat існує" (Test-Path $repos) "клонувати dxgat/* у G:\deepx_gat"
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
Write-Host ("   модулів з main.py: " + $mods.Count)

Write-Host "`n== Стенд стрімінгу ($stand)"
Check "G:\gat-streaming існує" (Test-Path $stand) ""
Check "streaming\contract.py" (Test-Path "$stand\streaming\contract.py") ""
Check "tools\compare_runs.py" (Test-Path "$stand\tools\compare_runs.py") ""
Check "data\ (інференси/gt для рівня 2)" (Test-Path "$stand\data") "потрібні інференси з cv-modules-topics + gt_by_video.json"

Write-Host "`n== Python"
$py = (Get-Command python -ErrorAction SilentlyContinue)
Check "python у PATH" ($null -ne $py) ""
if ($py) {
  foreach ($pkg in @("openpyxl", "pytest")) {
    $r = python -c "import $pkg" 2>$null; Check "pip: $pkg" ($LASTEXITCODE -eq 0) "pip install $pkg"
  }
}

Write-Host "`n== Git-доступ (без запитів пароля)"
$env:GIT_TERMINAL_PROMPT = "0"
foreach ($u in @("https://gitlab.com/dxgat/detectors/general_model.git", "https://gitlab.com/dxgat/utils/db_worker.git")) {
  $out = git ls-remote --heads $u 2>&1 | Select-Object -First 1
  Check $u ($out -match "refs/heads") "перевірити креденшели GitLab (Git Credential Manager)"
}

Write-Host "`nГотово. Далі: cd $root; claude"
