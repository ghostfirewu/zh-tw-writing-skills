"""rewrite_diff.py 的驗收測試。用法：python3 tests/test_rewrite_diff.py（全過印 ALL PASS）"""
import importlib.util
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.environ.get('REWRITE_DIFF', os.path.join(ROOT, 'skills', 'zh-tw-anti-slop', 'scripts', 'rewrite_diff.py'))
spec = importlib.util.spec_from_file_location('rewrite_diff', SCRIPT)
rd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rd)
failures = []


def expect(cond, name):
    print(('  ok   ' if cond else '  FAIL ') + name)
    if not cond:
        failures.append(name)


def marker(res, cat):
    return next((m for m in res['語氣用語'] if m['類別'] == cat), None)


# 數字：加料與漏掉
r = rd.compare('年費 1,200 元，週一起受理。', '年費 1,200 元，週一起受理，24 小時內處理。')
expect(r['數字']['多出來'] == ['24小時'], '多出來的數字（24 小時）')
r = rd.compare('約 42% 的人回覆。', '超過四成的人回覆。')
expect('42%' in r['數字']['不見了'], '精確數字被改成概略說法（42% 不見了）')
r = rd.compare('2026 年 9 月 30 日截止', '月底前截止')
expect(r['數字']['不見了'], '日期被縮寫（數字不見了）')

# 英文詞與引語
r = rd.compare('我們用 Python 寫的。', '我們用 Python 和 Rust 寫的。')
expect(r['英文詞']['多出來'] == ['Rust'], '多出來的英文詞（Rust）')
r = rd.compare('他說「明天再談」。', '他說「明天再說」。')
expect(r['引號內容']['多出來'] == ['明天再說'] and r['引號內容']['不見了'] == ['明天再談'], '引語被改字')

# 語氣強度
r = rd.compare('這可能是原因之一。', '這是原因之一。')
m = marker(r, '推測')
expect(m and m['強度可能改高'], '推測詞被刪 → 強度可能改高')
r = rd.compare('他協助這個專案。', '他負責這個專案。')
expect(marker(r, '責任') and marker(r, '責任')['強度可能改高'], '協助 → 負責：責任變重')
r = rd.compare('會員可退費，但限 7 天內。', '會員可退費。')
expect(marker(r, '範圍限定')['強度可能改高'], '但書被刪')
r = rd.compare('功能規劃中。', '功能已上線。')
expect(marker(r, '進行中')['強度可能改高'] and marker(r, '完成度')['強度可能改高'], '規劃中 → 已上線')
r = rd.compare('這是原因之一。', '這可能是原因之一。')
m = marker(r, '推測')
expect(m and not m['強度可能改高'], '加上推測詞＝強度變低，不算改高（仍列出增減）')

# 不誤報
r = rd.compare('團隊在三月完成測試，回應時間從 3 秒降到 1 秒。', '三月，團隊完成測試，回應時間從 3 秒降到 1 秒。')
expect(not rd.needs_review(r), '只調語序、數字不變 → 不需確認')
r = rd.compare('用 `git status` 確認', '先用 `git log` 確認')
expect(not r['英文詞']['多出來'], '行內程式碼不比對')
r = rd.compare('這點**很重要**。', '這點很重要。')
expect(not rd.needs_review(r), '只拿掉粗體 → 不需確認')

# 審查回歸：長引語、範圍限定、量詞、「不但」
long_b = '他說「' + '這件事情從頭到尾都是我們團隊花了整整三個月才完成的，其中最困難的是資料清理，因為原始資料分散在五個不同的系統裡面' + '」。'
long_a = long_b.replace('最困難', '最簡單')
r = rd.compare(long_b, long_a)
expect(r['引號內容']['多出來'] and r['引號內容']['不見了'], '超過 40 字的引語被改字也抓得到')
r = rd.compare('只有會員可以報名，名額有限。', '會員可以報名。')
expect(marker(r, '範圍限定') and marker(r, '範圍限定')['強度可能改高'], '「只有」「名額有限」被刪 → 範圍限定變少')
r = rd.compare('他不但會寫程式，還會設計。', '他會寫程式，也會設計。')
expect(marker(r, '範圍限定') is None, '「不但」不算範圍限定')
r = rd.compare('這是一個值得深思的問題。', '這個問題值得深思。')
expect(not r['數字']['不見了'], '刪冗餘量詞「一個」不算數字不見')
r = rd.compare('因此決定延期。', '決定延期。')
expect(rd.needs_review(r), '有任何語氣用語增減就回 1（不只⚠️項）')

for b0, a0, name in (('花了三個月', '花了兩個月', '三個月→兩個月'), ('休息三天', '休息五天', '三天→五天'),
                     ('等三週', '等兩週', '三週→兩週'), ('三十位講者', '五十位講者', '三十位→五十位'),
                     ('見第三章', '見第五章', '第三章→第五章')):
    r = rd.compare(b0, a0)
    expect(r['數字']['多出來'] and r['數字']['不見了'], f'中文數字：{name}')
r = rd.compare('筆記不僅僅是紀錄，它更是思考的延伸。', '筆記是思考的延伸。')
expect(marker(r, '範圍限定') is None, '刪二元對比「不僅僅」不算範圍限定變少')
r = rd.compare('僅限會員報名。', '會員可以報名。')
expect(marker(r, '範圍限定') and marker(r, '範圍限定')['強度可能改高'], '「僅限」被刪仍要抓')

# 命令列與結束代碼
d = tempfile.mkdtemp()
b, a = os.path.join(d, 'b.md'), os.path.join(d, 'a.md')
open(b, 'w', encoding='utf-8').write('年費 1,200 元')
open(a, 'w', encoding='utf-8').write('年費 1,200 元，現在續約最划算，保證滿意')
p = subprocess.run([sys.executable, SCRIPT, b, a], capture_output=True)
out = p.stdout.decode('utf-8')
expect(p.returncode == 1 and '保證' in out, 'CLI：有加料 → 結束代碼 1')
open(a, 'w', encoding='utf-8').write('年費是 1,200 元')
p = subprocess.run([sys.executable, SCRIPT, b, a], capture_output=True)
expect(p.returncode == 0, 'CLI：等義改寫 → 結束代碼 0')
p = subprocess.run([sys.executable, SCRIPT, b, os.path.join(d, 'none.md')], capture_output=True)
expect(p.returncode == 2, 'CLI：檔案不存在 → 結束代碼 2')

print()
if failures:
    print(f'{len(failures)} 項失敗')
    sys.exit(1)
print('ALL PASS')
