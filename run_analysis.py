"""Run local NLP, dbt build/tests, and report export from the project root."""
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent
os.chdir(root)
subprocess.run([sys.executable, 'scripts/features.py'], check=True)
from dbt.cli.main import dbtRunner
result = dbtRunner().invoke(['build', '--profiles-dir', '.', '--project-dir', '.', '--no-use-colors'])
if not result.success:
    raise SystemExit('dbt build failed; report was not updated')
subprocess.run([sys.executable, 'scripts/export_report.py'], check=True)
subprocess.run([sys.executable, 'scripts/export_portfolio.py'], check=True)
