"""專案層個人化設定（.zh-tw-writing/）的驗收測試。用法：python3 tests/test_overlay.py（全過印 ALL PASS）"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZC = os.path.join(ROOT, 'skills', 'zh-tw-guard', 'scripts', 'zhtw_check.py')
SS = os.path.join(ROOT, 'skills', 'zh-tw-anti-slop', 'scripts', 'slop_scan.py')
HOOK = os.path.join(ROOT, 'hooks', 'zhtw_post_write.py')
failures = []


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def expect(cond, name):
    print(('  ok   ' if cond else '  FAIL ') + name)
    if not cond:
        failures.append(name)


# 測試不受執行環境的專案設定影響
for k in ('ZHTW_WRITING_DIR', 'CLAUDE_PROJECT_DIR'):
    os.environ.pop(k, None)

zc, ss = load(ZC, 'zhtw_check'), load(SS, 'slop_scan')

proj = tempfile.mkdtemp()
cfg = os.path.join(proj, '.zh-tw-writing')
os.makedirs(cfg)
with open(os.path.join(cfg, 'terms.tsv'), 'w', encoding='utf-8') as f:
    f.write('# 專案追加\n抓手\t著力點\tA\n雲盤\t雲端硬碟\tA\n')
with open(os.path.join(cfg, 'slop.tsv'), 'w', encoding='utf-8') as f:
    f.write('# 專案追加\n全鏈路\t專案口頭禪\t講清楚是哪幾段流程\n')
with open(os.path.join(cfg, 'allow.txt'), 'w', encoding='utf-8') as f:
    f.write('# 專名白名單\n一站式學習平台\n张三丰\n')

empty = tempfile.mkdtemp()

# 找設定資料夾
expect(zc.find_config_dir(cwd=proj) == cfg, '目前所在目錄底下的 .zh-tw-writing 找得到')
expect(zc.find_config_dir(cwd=empty) is None, '沒有設定資料夾 → None')
expect(zc.find_config_dir(explicit=cfg, cwd=empty) == cfg, '明確指定的路徑優先')
os.environ['CLAUDE_PROJECT_DIR'] = proj
expect(zc.find_config_dir(cwd=empty) == cfg, 'CLAUDE_PROJECT_DIR 底下的設定找得到')
del os.environ['CLAUDE_PROJECT_DIR']

conf = zc.load_config(cfg)

# 用語：追加、覆寫
hits = zc.check_text('我們用雲盤存檔', only=('用語',), config=conf)
expect([h['match'] for h in hits] == ['雲盤'], '追加的用語抓得到（雲盤）')
sug = {h['match']: h['suggestion'] for h in zc.check_text('找到抓手', only=('用語',), config=conf)}
expect(sug.get('抓手') == '著力點', '同一個詞以專案設定覆寫內建建議')
expect(not zc.check_text('我們用雲盤存檔', only=('用語',)), '不帶設定時不受影響')

# 白名單
stats = {}
hits = zc.check_text('作者张三丰說這是一站式學習平台', config=conf, stats=stats)
expect(not any(h['match'] in ('张', '三丰') or '张' in h['match'] for h in hits), '白名單的專名不報簡體')
expect(stats.get('allowed', 0) >= 1, '統計被白名單略過的筆數')
expect(any(h['category'] == '簡體' for h in zc.check_text('作者张三丰', config=None)), '不帶設定時簡體照報')

# 命令列：自動讀設定、--no-config、--config-dir、尾行說明
doc = os.path.join(proj, 'a.md')
with open(doc, 'w', encoding='utf-8') as f:
    f.write('我們用雲盤存檔，作者张三丰\n')
p = subprocess.run([sys.executable, ZC, 'a.md'], capture_output=True, cwd=proj)
out = p.stdout.decode('utf-8')
expect('雲盤' in out and '张' not in out.split('共')[0], 'CLI 自動讀目前目錄的設定')
expect('白名單' in out and '專案設定' in out, 'CLI 尾行說明套用了專案設定與白名單')
p = subprocess.run([sys.executable, ZC, '--no-config', 'a.md'], capture_output=True, cwd=proj)
out = p.stdout.decode('utf-8')
expect('雲盤' not in out and '张' in out, '--no-config 關閉專案設定')
p = subprocess.run([sys.executable, ZC, '--config-dir', cfg, doc], capture_output=True, cwd=empty)
expect('雲盤' in p.stdout.decode('utf-8'), '--config-dir 指定設定資料夾')

# AI 腔掃描
sconf = ss.load_config(cfg)
expect([h['match'] for h in ss.scan('打通全鏈路', config=sconf)] == ['全鏈路'], 'AI 腔：追加的詞條抓得到')
expect(not ss.scan('歡迎使用一站式學習平台', config=sconf), 'AI 腔：白名單的專名不報（一站式）')
expect(ss.scan('歡迎使用一站式學習平台'), 'AI 腔：不帶設定時照報')
p = subprocess.run([sys.executable, SS, 'a.md'], capture_output=True, cwd=proj)
expect('專案設定' in p.stdout.decode('utf-8'), 'AI 腔 CLI 尾行說明套用了專案設定')

# hook：讀 CLAUDE_PROJECT_DIR 的白名單
env = dict(os.environ, CLAUDE_PROJECT_DIR=proj)
env.pop('ZHTW_GUARD_OFF', None)
payload = json.dumps({'tool_name': 'Write', 'cwd': proj,
                      'tool_input': {'file_path': os.path.join(proj, 'b.md'), 'content': '作者张三丰'}},
                     ensure_ascii=False).encode('utf-8')
p = subprocess.run([sys.executable, HOOK], input=payload, capture_output=True, env=env)
expect(p.returncode == 0, 'hook：白名單的專名不提醒')
payload2 = payload.replace('张三丰'.encode('utf-8'), '这个'.encode('utf-8'))
p = subprocess.run([sys.executable, HOOK], input=payload2, capture_output=True, env=env)
expect(p.returncode == 2, 'hook：白名單以外的簡體照提醒')

# 壞掉的設定不讓工具掛掉
bad = tempfile.mkdtemp()
os.makedirs(os.path.join(bad, '.zh-tw-writing'))
with open(os.path.join(bad, '.zh-tw-writing', 'terms.tsv'), 'wb') as f:
    f.write(b'\xff\xfe broken\tonly-two-cols\n')
p = subprocess.run([sys.executable, ZC, '-'], input='這個'.encode('utf-8'), capture_output=True, cwd=bad)
expect(p.returncode in (0, 1), '設定檔格式錯誤時照常執行（略過壞列）')

# 審查回歸：壞列、指定路徑不存在、白名單與占位
bad2 = tempfile.mkdtemp()
os.makedirs(os.path.join(bad2, '.zh-tw-writing'))
with open(os.path.join(bad2, '.zh-tw-writing', 'slop.tsv'), 'wb') as f:
    f.write('只有樣式一欄\n'.encode('utf-8') + b'\xff\xfe\tbad\tx\n' + '正常詞\t類別\t改法\n'.encode('utf-8'))
c2 = ss.load_config(os.path.join(bad2, '.zh-tw-writing'))
expect([rx.pattern for rx, _, _ in c2['patterns']] == ['正常詞'], 'slop.tsv：缺類別欄、含亂碼的列都略過')
p = subprocess.run([sys.executable, ZC, '--config-dir', os.path.join(empty, 'nope'), '-'], input=b'x', capture_output=True)
expect(p.returncode == 2, 'zhtw_check：--config-dir 指到不存在的路徑 → 結束代碼 2')
p = subprocess.run([sys.executable, SS, '--config-dir', os.path.join(empty, 'nope'), '-'], input=b'x', capture_output=True)
expect(p.returncode == 2, 'slop_scan：--config-dir 指到不存在的路徑 → 結束代碼 2')
ov = tempfile.mkdtemp()
with open(os.path.join(ov, 'slop.tsv'), 'w', encoding='utf-8') as f:
    f.write('甲乙\t測試\t改\n乙丙丁\t測試\t改\n')
with open(os.path.join(ov, 'allow.txt'), 'w', encoding='utf-8') as f:
    f.write('甲乙\n')
expect([h['match'] for h in ss.scan('甲乙丙丁', patterns=[], config=ss.load_config(ov))] == ['乙丙丁'],
       'slop：被白名單略過的命中不占位，重疊的另一個命中照報')
with open(os.path.join(ov, 'terms.tsv'), 'w', encoding='utf-8') as f:
    f.write('甲乙\t甲\tA\n乙丙丁\t乙\tA\n')
hits = zc.check_text('甲乙丙丁', only=('用語',), config=zc.load_config(ov))
expect([h['match'] for h in hits] == ['乙丙丁'], '用語：被白名單略過的命中不占位')

# 第二輪回歸：' 註解、略過筆數
with open(os.path.join(ov, 'slop.tsv'), 'w', encoding='utf-8') as f:
    f.write("'註解\t假類別\tx\n甲乙\t測試\t改\n乙丙丁\t測試\t改\n")
expect(all(rx.pattern != "'註解" for rx, _, _ in ss.load_config(ov)['patterns']), "slop.tsv：' 開頭的列是註解")
st = {}
ss.scan('甲乙甲乙', patterns=[], config=ss.load_config(ov), stats=st)
expect(st.get('allowed') == 2, f"slop：略過筆數同一段只算一次（{st.get('allowed')}）")
st = {}
zc.check_text('`甲乙` 甲乙', only=('用語',), level=('A',), config=zc.load_config(ov), stats=st)
expect(st.get('allowed') == 1, f"用語：程式碼裡的不計入略過筆數（{st.get('allowed')}）")

print()
if failures:
    print(f'{len(failures)} 項失敗')
    sys.exit(1)
print('ALL PASS')
