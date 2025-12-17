#!/usr/bin/env bash
# run_tests.sh - Run pytest with coverage and HTML report
#run_tests.sh -k "leaf_keys" -q
# Usage: ./run_tests.sh [additional pytest args]

set -euo pipefail

# 可修改的參數
SOURCE="core"                   # 要測 coverage 的 package/資料夾
COV_REPORT_DIR="htmlcov"        # HTML coverage report 目錄
PYTEST_ARGS="-v --maxfail=1"    # 預設 pytest 參數

# 使用 pytest via python -m pytest（較保險）
PYTEST="python -m pytest"

# 清理舊報告
rm -rf "${COV_REPORT_DIR}" .pytest_cache .coverage || true

# 執行測試並產生 coverage（terminal + html）
echo "Running tests: ${PYTEST} ${PYTEST_ARGS} --cov=${SOURCE} --cov-report=term-missing --cov-report=html \"$@\""
${PYTEST} ${PYTEST_ARGS} --cov="${SOURCE}" --cov-report=term-missing --cov-report=html "$@"
RC=$?

if [ $RC -ne 0 ]; then
  echo "Tests failed (exit ${RC})"
  exit $RC
fi

echo "Tests passed. HTML coverage available at ./${COV_REPORT_DIR}/index.html"
exit 0
