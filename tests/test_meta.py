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

# 原始碼與文字檔中段不得含字面 U+FEFF（BOM）：它是不可見字元，編輯工具看不出差異，
# 字串比對與 diff 會靜默失配。程式裡要表示 BOM 一律寫轉義。檔案開頭的 BOM 是編碼標記，不算。
TEXT_EXT = ('.py', '.sh', '.md', '.json', '.tsv', '.txt', '.yml', '.yaml', '.ini', '.bat', '.ps1')
BOM = bytes([0xEF, 0xBB, 0xBF])
bom_hits = []
for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d != '.git']
    for f in files:
        if f.endswith(TEXT_EXT):
            path = os.path.join(base, f)
            with open(path, 'rb') as fh:
                if fh.read().find(BOM, 1) > 0:
                    bom_hits.append(os.path.relpath(path, ROOT))
expect(not bom_hits, f'文字檔中段沒有字面 BOM（命中：{bom_hits}）')

print()
if failures:
    print(f'{len(failures)} 項失敗')
    sys.exit(1)
print('ALL PASS')
