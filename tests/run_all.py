"""跑全部測試：python3 tests/run_all.py（全過以代碼 0 結束）"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIT = os.path.join(ROOT, 'skills', 'manuscript-check', 'scripts', 'tests')
SUITES = [
    os.path.join(ROOT, 'tests', 'test_zhtw_check.py'),
    os.path.join(ROOT, 'tests', 'test_slop_scan.py'),
    os.path.join(ROOT, 'tests', 'test_hook.py'),
    os.path.join(KIT, 'test_all.py'),
    os.path.join(KIT, 'test_collate.py'),
    os.path.join(KIT, 'test_index.py'),
]
env = dict(os.environ, PYTHONIOENCODING='utf-8')
failed = []
for s in SUITES:
    p = subprocess.run([sys.executable, s], capture_output=True, env=env)
    out = p.stdout.decode('utf-8', errors='replace')
    ok = p.returncode == 0 and 'ALL PASS' in out
    print(('PASS ' if ok else 'FAIL ') + os.path.relpath(s, ROOT))
    if not ok:
        failed.append(s)
        print(out[-2000:], p.stderr.decode('utf-8', errors='replace')[-2000:])
sys.exit(1 if failed else 0)
