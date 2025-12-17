# run_tests.ps1 - Run pytest with coverage
param(
  [Parameter(ValueFromRemainingArguments=$true)]
  [String[]] $ArgsPytest
)

$Source = "core"
$CovDir = "htmlcov"

# remove old
Remove-Item -Recurse -Force $CovDir -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force .pytest_cache -ErrorAction SilentlyContinue
Remove-Item -Force .coverage -ErrorAction SilentlyContinue

$pytestArgs = @("-v", "--maxfail=1", "--cov=$Source", "--cov-report=term-missing", "--cov-report=html")
$pytestArgs += $ArgsPytest

Write-Host "Running: python -m pytest $($pytestArgs -join ' ')"
$proc = Start-Process -FilePath "python" -ArgumentList @("-m","pytest") + $pytestArgs -NoNewWindow -Wait -PassThru

if ($proc.ExitCode -ne 0) {
    Write-Error "Tests failed (exit $($proc.ExitCode))"
    exit $proc.ExitCode
}

Write-Host "Tests passed. HTML coverage at .\$CovDir\index.html"
exit 0
