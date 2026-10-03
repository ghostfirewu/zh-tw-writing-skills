"""發布相關的一致性檢查。用法：python3 tests/test_meta.py（全過印 ALL PASS）"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
failures = []


def expect(cond, name):
    print(('  ok   ' if cond else '  FAIL ') + name)
    if not cond:
        failures.append(name)


version = json.load(open(os.path.join(ROOT, '.claude-plugin', 'plugin.json'), encoding='utf-8'))['version']
log = open(os.path.join(ROOT, 'CHANGELOG.md'), encoding='utf-8').read()
m = re.search(r'^## v(\S+)', log, re.M)
expect(m and m.group(1) == version, f'CHANGELOG 最上面的版本（{m and m.group(1)}）等於 plugin.json 的版本（{version}）')
mk = json.load(open(os.path.join(ROOT, '.claude-plugin', 'marketplace.json'), encoding='utf-8'))
expect(all('version' not in p for p in mk['plugins']), 'marketplace.json 不另寫版本（以 plugin.json 為準）')

# 自動建立 Release 時，說明取自 CHANGELOG 對應段落；那一段必須存在且不是空的
import subprocess  # noqa: E402
SCRIPT = os.path.join(ROOT, '.github', 'scripts', 'changelog_section.py')
p = subprocess.run([sys.executable, SCRIPT, version], capture_output=True)
expect(p.returncode == 0 and p.stdout.strip(), f'CHANGELOG 有 v{version} 的說明段落（Release 說明用）')
p = subprocess.run([sys.executable, SCRIPT, '0.0.0'], capture_output=True)
expect(p.returncode == 1, '找不到的版本 → 結束代碼 1')
p = subprocess.run([sys.executable, SCRIPT, '1.1.0'], capture_output=True)
out = p.stdout.decode('utf-8')
expect('## v' not in out and 'v1.0.0' not in out, '只取該版一段，不混入下一版')

print()
if failures:
    print(f'{len(failures)} 項失敗')
    sys.exit(1)
print('ALL PASS')
