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

print()
if failures:
    print(f'{len(failures)} 項失敗')
    sys.exit(1)
print('ALL PASS')
