"""第四期（索引頁碼）驗收測試。

夾具：index_typeset.pdf（2 頁未編頁碼的前頁＋6 頁正文，正文頁碼 1–6、有書眉與註腳），
由 make_index_fixture.ps1 依 index_fixture.json 產生（需要 Word）；詞表是 index_terms.txt。
用法：python tests/test_index.py
"""
import configparser
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from checks import index_pages, pdf_text  # noqa: E402
from checks.common import load_config  # noqa: E402

failures = []


def expect(cond, label):
    print(('  ok   ' if cond else '  FAIL ') + label)
    if not cond:
        failures.append(label)


cfg = load_config(os.path.join(os.path.dirname(HERE), '設定', '設定.ini'))
sec = cfg['索引']
pdf = pdf_text.load(os.path.join(HERE, 'index_typeset.pdf'), cfg)
entries = index_pages.load_terms(os.path.join(HERE, 'index_terms.txt'))
index_pages.find_pages(entries, pdf)
lines, table, missing, off, note = index_pages.build(entries, pdf, sec)
for ln in lines:
    print('     ', ln)
got = {row[0]: row[2] for row in table}

print('[頁碼換算]')
expect(off == 2, f'頁碼差 2（前頁 2 頁不編頁碼）；實得 {off}')

print('[抓頁碼]')
expect(got['生態治理'] == '1–3', '連續三頁合併成 1–3；目錄頁（前頁）的「生態治理」不列')
expect(got['治理>多中心治理'] == '3', '子條目')
expect(got['資本'] == '5', '排除詞：「資本主義」不算，只剩書頁 5')
expect(got['公共財'] == '4, 5', '註腳（書頁 4）也算')
expect(got['Ostrom'] == '5', '英文完整單字：Ostromian 不算')
expect(got['AI'] == '', '英文完整單字：MAIN 裡的 AI 不算')
expect(got['書眉專用詞'] == '', '只出現在書眉的詞不算')
expect('生態系　見 生態治理' in lines, '純參見條目')
expect('　多中心治理　3' in lines, '子條目縮排')
expect({e.heading for e in missing} == {'AI', '書眉專用詞', '不存在的詞'}, '找不到的詞條列出')
expect(not any(ln.startswith(('AI', '書眉專用詞', '不存在的詞')) for ln in lines), '找不到的詞條不印進索引')

state = {row[0]: row[5] for row in table}
expect('上層詞條沒有寫在前面' in state['治理>多中心治理'], '子條目的上層詞條「治理」不在詞表裡 → 提醒')

dang = index_pages.build([index_pages.Entry('甲', ['甲'], see='不存在')], pdf, sec)[1]
expect('不是索引裡的詞條' in dang[0][5] and '不是索引裡的詞條' not in state['生態系'], '參見指向不存在的詞條 → 提醒；指向存在的不提醒')

print('[格式選項]')
alt = configparser.ConfigParser()
alt.read_dict({'x': {'範圍符號': '-', '頁碼分隔': '、', '註腳標記': 'n', '合併連續頁': '否'}})
expect(index_pages.fmt_pages({1, 2, 3}, {4}, 0, alt['x']) == '1、2、3、4n', '不合併連續頁、註腳加 n、自訂分隔')
expect(index_pages.fmt_pages({3, 4, 5, 9}, set(), 2, sec) == '1–3, 7', '依頁碼差換算並合併')

print('[筆畫排序]')
words = ['黃金', 'Ostrom', '草原', '十', '一二', 'apple', '近代', '乙', '人']
es = [index_pages.Entry(w, [w]) for w in words] + [index_pages.Entry('人>後設', ['後設']), index_pages.Entry('人>多元', ['多元'])]
order = [e.heading for e in index_pages.sort_entries(es)]
expect(order == ['一二', '乙', '人', '人>多元', '人>後設', '十', '近代', '草原', '黃金', 'apple', 'Ostrom'],
       f'筆畫少的在前（一1 乙1 人2 十2 近8 草10 黃12；同筆畫依部首）、子條目跟在上層後面、西文放後面；實得 {order}')
expect(index_pages.strokes()['近'][0] == 8 and index_pages.strokes()['草'][0] == 10, '筆畫依正體算法：近 8、草 10')
cfg2 = configparser.ConfigParser()
cfg2.read_dict({'x': dict(sec.items())})
cfg2['x']['排序'] = '筆畫'
cfg2['x']['筆畫標題'] = '是'
es2 = index_pages.find_pages(index_pages.load_terms(os.path.join(HERE, 'index_terms.txt')), pdf)
lines2 = index_pages.build(es2, pdf, cfg2['x'])[0]
expect(lines2[0] == '【4 畫】' and '【13 畫】' in lines2 and '【西文】' in lines2 and '【10 畫】' not in lines2,
       f'筆畫標題；只印有內容的組（書眉專用詞找不到，10 畫整組不出現）；實得 {lines2}')

print('[行末斷字]')
s = pdf_text.Stream()
s.add('the gover-', 1)
s.line_ends.add(len(s.text) - 1)
s.add('nance of meta-', 1)
s.line_ends.add(len(s.text) - 1)
s.add('Governor', 2)
text, idx = index_pages._dehyphen(s)
expect('governance' in text, '行末「gover-」接下一行小寫開頭 → 接回')
expect('meta-Governor' in text, '下一行大寫開頭 → 保留連字號')

print()
if failures:
    print(f'{len(failures)} FAIL')
    sys.exit(1)
print('ALL PASS')
