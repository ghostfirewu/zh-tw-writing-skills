"""zh-tw-guard 檢查器的驗收測試。用法：python3 tests/test_zhtw_check.py（全過印 ALL PASS，否則以代碼 1 結束）"""
import os
import sys
import importlib.util

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.environ.get('ZHTW_CHECK', os.path.join(ROOT, 'skills', 'zh-tw-guard', 'scripts', 'zhtw_check.py'))
spec = importlib.util.spec_from_file_location('zhtw_check', SCRIPT)
zc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(zc)

failures = []


def expect(cond, name):
    print(('  ok   ' if cond else '  FAIL ') + name)
    if not cond:
        failures.append(name)


def matches(text, cat=None, **kw):
    return [h['match'] for h in zc.check_text(text, **kw) if cat is None or h['category'] == cat]


# 簡體字
expect(len(zc.gb_only_chars()) == 2380, 'GB2312 有、Big5 無的漢字共 2380 個')
expect(matches('这个东西', '簡體') == ['这', '个', '东'], '抓到簡體字（这个东）')
expect(matches('這個東西很好', '簡體') == [], '正體字不誤報')

# 一簡多繁
expect(matches('我們以后再說', '一簡多繁') == ['以后'], '一簡多繁：以后')
expect(matches('皇后與太后', '一簡多繁') == [], '一簡多繁：排除詞（皇后、太后）不報')
expect(matches('距離三公里', '一簡多繁') == [], '一簡多繁：公里不報')

# 錯轉
expect(matches('他的頭發很長', '錯轉') == ['頭發'], '錯轉繁：頭發')
expect(matches('他的頭髮很長', '錯轉') == [], '錯轉繁：正確寫法不報')

# 用語：先比長詞
expect(matches('音視頻剪輯', '用語') == ['音視頻'], '長詞優先：音視頻只報一次，不再報視頻')
expect(matches('短視頻平台', '用語') == ['短視頻'], '長詞優先：短視頻')
expect(matches('他是程序員', '用語') == ['程序員'], '長詞優先：程序員不被拆成程序')
sug = {h['match']: h['suggestion'] for h in zc.check_text('看視頻', only=('用語',))}
expect(sug.get('視頻') == '影片', '視頻 → 影片')

# 用語：排除詞與級別
expect(matches('申請程序很繁瑣', '用語') == [], '排除詞：申請程序不報')
expect(matches('這個程序跑不動', '用語') == ['程序'], 'B 級：程序（程式義）照報')
expect(matches('水平面上', '用語') == [], '排除詞：水平面不報')
expect(matches('質量守恆定律', '用語') == [], '排除詞：質量守恆不報')
expect(matches('在線上互動', '用語') == [], '排除詞：在線上不報')
expect(matches('這個程序跑不動', '用語', level=('A',)) == [], '--level A 時不報 B 級')

# 程式碼區塊不查用語、仍查簡體
md = '正文的視頻\n```\nvideo = "視頻"\n这\n```\n行內 `視頻` 不算'
hits = zc.check_text(md)
expect([h['line'] for h in hits if h['category'] == '用語'] == [1], '程式碼區塊與行內程式碼不查用語')
expect([h['line'] for h in hits if h['category'] == '簡體'] == [4], '程式碼區塊內仍查簡體字')

# 台灣正常用法不誤報（對抗審查抓到的誤報，留作回歸測試）
for txt in ('交互作用', '菠蘿麵包', '仿真槍', '社會網絡', '摩托車', '農田渠道', '資本積累'):
    expect(matches(txt, '用語') == [], f'不誤報：{txt}')
expect(matches('系上的老師', '一簡多繁') == [], '不誤報：系上的老師')
expect(all(h['level'] == 'B' for h in zc.check_text('土豆', only=('用語',))), '土豆只列 B 級（台灣多指花生）')
sug = {h['match']: h['suggestion'] for h in zc.check_text('共情', only=('用語',))}
expect(sug.get('共情') == '同理／同理心', '共情 → 同理／同理心（不是共鳴）')

# 命令列：--only 逗號分隔，檔名放前放後都可以
import subprocess  # noqa: E402
import tempfile  # noqa: E402
with tempfile.NamedTemporaryFile('w', suffix='.md', delete=False, encoding='utf-8') as f:
    f.write('這個視頻\n以后再說\n')
for args in (['--only', '簡體,一簡多繁', f.name], [f.name, '--only', '簡體,一簡多繁']):
    p = subprocess.run([sys.executable, SCRIPT] + args, capture_output=True)
    out = p.stdout.decode('utf-8')
    expect(p.returncode == 1 and '以后' in out and '視頻' not in out, f'CLI：{" ".join(a for a in args if a != f.name)}（檔名{"在後" if args[-1] == f.name else "在前"}）')
p = subprocess.run([sys.executable, SCRIPT, '--only', '不存在', f.name], capture_output=True)
expect(p.returncode == 2, 'CLI：--only 給錯類別 → 結束代碼 2')
p = subprocess.run([sys.executable, SCRIPT, '--level', 'A', '-'], input='申請程序\n'.encode('utf-8'), capture_output=True)
expect(p.returncode == 0, 'CLI：標準輸入、只有 B 級語境詞 → 結束代碼 0')
os.unlink(f.name)

# 結束代碼語意
expect(zc.is_blocking({'category': '用語', 'level': 'B'}) is False, 'B 級用語不算需處理項')
expect(zc.is_blocking({'category': '簡體', 'level': ''}) is True, '簡體字算需處理項')

# 跨詞誤判：「構建」不能命中「架構＋建議」
expect(matches('附上書稿架構建議', '用語') == [], '排除詞：架構建議不報（架構＋建議）')
expect(matches('構建資料模型', '用語') == ['構建'], 'A 級：構建照報')

# 兩份共用清單必須一致（manuscript-check 的設定檔是 zh-tw-guard 的複本）
for name in ('一簡多繁.txt', '錯轉.txt'):
    a = open(os.path.join(ROOT, 'skills', 'zh-tw-guard', 'data', name), encoding='utf-8-sig').read()
    b = open(os.path.join(ROOT, 'skills', 'manuscript-check', 'scripts', '設定', name), encoding='utf-8-sig').read()
    expect(a == b, f'{name} 兩份一致（zh-tw-guard/data 與 manuscript-check/scripts/設定）')

# references/terms.md 的表格詞與 data/terms.tsv 必須對得上（刻意不收的詞列在白名單）
import re  # noqa: E402
NOT_IN_TSV = {'通過', '挺（副詞）', '句末「來著」', '泛用動詞「整」「搞」'}
md = open(os.path.join(ROOT, 'skills', 'zh-tw-guard', 'references', 'terms.md'), encoding='utf-8').read()
tsv = {r[0] for r in zc.terms()}
md_words = set()
for line in md.splitlines():
    if not line.startswith('|') or '---' in line:
        continue
    cells = [c.strip() for c in line.strip('|').split('|')]
    if cells[0] in ('中國用語', '詞', '痕跡'):
        continue
    if '→' in cells[0]:
        md_words.add(cells[0].split('→')[0].strip())
        continue
    for c in (cells[0], cells[2] if len(cells) == 4 else None):
        if c and c != '—':
            md_words.update(w.strip() for w in re.split(r'\s*[／/]\s*', c))
missing = sorted(md_words - tsv - NOT_IN_TSV)
expect(not missing, f'terms.md 的詞都在 terms.tsv（缺：{missing}）')
extra = sorted(w for w in tsv if w not in md)
expect(not extra, f'terms.tsv 的詞都寫在 terms.md（多：{extra}）')

print()
if failures:
    print(f'{len(failures)} 項失敗')
    sys.exit(1)
print('ALL PASS')
