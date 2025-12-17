@echo off
setlocal enabledelayedexpansion
REM run_tests.bat - Run pytest with coverage
REM Usage: run_tests.bat [pytest-args]

REM ===========================
REM Default config
REM ===========================
set SOURCE=src
set COV_REPORT_DIR=htmlcov
set LOG_LEVEL=ERROR
set MAXFAIL=10

REM ===========================
REM Argument Parsing
REM ===========================
REM First argument may override LOG_LEVEL
if not "%1"=="" (
  set LOG_LEVEL=%1
  shift
)

REM Collect remaining args AFTER shift
set args=

:collect
if "%1"=="" goto run
set args=!args! %1
shift
goto collect

:run
echo LOG_LEVEL = %LOG_LEVEL%


REM ===========================
REM Cleanup old coverage (best-effort)
REM ===========================
if exist %COV_REPORT_DIR% rmdir /s /q %COV_REPORT_DIR%
if exist .pytest_cache rmdir /s /q .pytest_cache
if exist .coverage del /q .coverage


REM ===========================
REM Run tests
REM ===========================
echo.
echo Running: python -m pytest -s -vv --log-cli-level=%LOG_LEVEL% --maxfail=%MAXFAIL% --cov=%SOURCE% --cov-report=term-missing --cov-report=html !args!

python -m pytest -s -vv --log-cli-level=%LOG_LEVEL% --maxfail=%MAXFAIL% --cov=%SOURCE% --cov-report=term-missing --cov-report=html !args!

if errorlevel 1 (
  echo Tests failed.
  exit /b 1
)

echo Tests passed. HTML coverage in %COV_REPORT_DIR%\index.html
exit /b 0
