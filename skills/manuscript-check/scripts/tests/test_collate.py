"""第三期（排版比對）驗收測試。

夾具：collate_src.docx（定稿）與 collate_typeset.pdf（埋了 8 處差異、加上頁首與頁碼的排版稿），
由 make_pdf_fixture.ps1 依 collate_fixture.json 產生（需要 Word）。
用法：python tests/test_collate.py
"""
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from checks import collate, docx_text, pdf_text, report  # noqa: E402
from checks.common import load_config  # noqa: E402

failures = []


def expect(cond, label):
    print(('  ok   ' if cond else '  FAIL ') + label)
    if not cond:
        failures.append(label)


cfg = load_config(os.path.join(os.path.dirname(HERE), '設定', '設定.ini'))
doc = docx_text.load(os.path.join(HERE, 'collate_src.docx'))
pdf = pdf_text.load(os.path.join(HERE, 'collate_typeset.pdf'), cfg)
res = collate.run(doc, pdf, cfg)
rows = [r[1:] for r in res.rows]   # 去掉分級欄，其餘欄位順序同舊版
for r in rows:
    print('     ', r[0], '|', r[4], '|', r[5], '|', r[3])


def find(cat, doc_has='', pdf_has=''):
    return [r for r in rows if r[0] == cat and doc_has in r[4] and pdf_has in r[5]]


print('[抽取]')
expect(pdf.printed.get(1) == '1', '從頁尾抓到書上頁碼')
expect(all('測試書名' not in r[5] for r in rows), '頁首沒有被當成差異')
expect(pdf.marks_dropped == 2, '移除 2 個上標注碼')

print('[埋入的差異]')
expect(bool(find('文字不同', '【測】', '【側】')), '改字：測→側（第 7 句）')
expect(bool(find('疑似漏段', '第15句')), '漏一整句：第 15 句')
expect(bool(find('數字不同', '【2】', '【3】')) or bool(find('數字不同', '22', '32')), '數字：22→32')
expect(bool(find('整段漏排', '整段漏掉')), '漏一整段')
expect(bool(find('標點不同', '【，】', '【。】')), '標點：，→。')
expect(bool(find('排版稿多了', '', '排版多出')), '多字：（排版多出）')
expect(bool([r for r in rows if r[6] == '註腳' and '【原】' in r[4] and '【改】' in r[5]]), '註腳改字：原→改')
expect(len(find('位置移動', '圖說')) >= 1, '圖說被移位判為「位置移動」')

print('[沒有多餘的差異]')
expect(len(rows) == 9, f'差異共 9 筆（8 處埋入，圖說移動會在原位與新位置各報一筆）；實得 {len(rows)} 筆')

print('[報表]')
out = os.path.join(tempfile.mkdtemp(), 'out.xlsx')
report.write(out, doc, {'比對': res}, extra=[('排版稿', 'collate_typeset.pdf')])
import openpyxl  # noqa: E402
wb = openpyxl.load_workbook(out)
expect(wb.sheetnames == ['總覽', '⑦ 排版比對', '已排除的頁首頁尾'], '報表三張工作表')

print()
if failures:
    print(f'{len(failures)} FAIL')
    sys.exit(1)
print('ALL PASS')
