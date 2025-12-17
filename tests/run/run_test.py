"""
#!/usr/bin/env python3
run_tests.py - cross-platform pytest runner with coverage

Usage:
   python run_tests.py           # run default
   python run_tests.py -k testname  # pass pytest args
"""

import sys
import shutil
import subprocess
from pathlib import Path

SOURCE = "core.lattix"
COV_REPORT_DIR = "htmlcov"

def main(argv):
   # remove old coverage artifacts (best-effort)
   for p in (COV_REPORT_DIR, ".pytest_cache", ".coverage"):
      path = Path(p)
      if path.exists():
         if path.is_dir():
            shutil.rmtree(path)
         else:
            path.unlink()

   pytest_cmd = [sys.executable, "-m", "pytest", "-v", "--maxfail=1",
                 f"--cov={SOURCE}", "--cov-report=term-missing", "--cov-report=html"]
   pytest_cmd += argv  # forward args
   print("Running:", " ".join(pytest_cmd))
   rc = subprocess.call(pytest_cmd)
   if rc != 0:
       print(f"pytest returned {rc}", file=sys.stderr)
   else:
       print(f"Tests passed. HTML coverage at ./{COV_REPORT_DIR}/index.html")
   return rc

if __name__ == "__main__":
   print(sys.executable)
   sys.exit(main(sys.argv[1:]))