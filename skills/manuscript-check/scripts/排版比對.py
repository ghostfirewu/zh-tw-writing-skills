"""排版比對：定稿 Word 檔與排版 PDF 逐字比對，產出 Excel 差異報表。只讀兩個檔案，不修改。

用法：
    python 排版比對.py 定稿.docx 排版稿.pdf
    python 排版比對.py 定稿.docx 排版稿.pdf --輸出 報表資料夾

也可以把兩個檔案一起拖放到「排版比對.bat」上（順序不拘）。
PDF 必須有文字層（排版軟體直接輸出的 PDF）；掃描檔沒有文字層，無法比對。只支援橫排。
"""
import argparse
import os
import sys
import time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from checks import collate, docx_text, pdf_text, report  # noqa: E402
from checks.common import load_config  # noqa: E402


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    ap = argparse.ArgumentParser(description='定稿與排版 PDF 逐字比對（規則式，不使用 AI）')
    ap.add_argument('檔案', nargs=2, help='定稿 .docx 與排版 .pdf（順序不拘）')
    ap.add_argument('--設定', default=os.path.join(HERE, '設定', '設定.ini'))
    ap.add_argument('--輸出', help='報表存放資料夾（預設與定稿同資料夾）')
    args = ap.parse_args()

    files = [os.path.abspath(f) for f in args.檔案]
    docx = [f for f in files if f.lower().endswith(('.docx', '.docm'))]
    pdf = [f for f in files if f.lower().endswith('.pdf')]
    if len(docx) != 1 or len(pdf) != 1:
        print('需要一個 .docx 和一個 .pdf')
        return 1

    cfg = load_config(args.設定)
    t0 = time.time()
    print(f'■ 定稿：{os.path.basename(docx[0])}')
    doc = docx_text.load(docx[0])
    print(f'■ 排版稿：{os.path.basename(pdf[0])}')
    pt = pdf_text.load(pdf[0], cfg)
    if not pt.main.text:
        print('  PDF 沒有文字層（可能是掃描檔），無法比對')
        return 1
    print(f'  {pt.n_pages} 頁，抽到正文 {len(pt.main.text):,} 字')
    res = collate.run(doc, pt, cfg)
    print(f'  差異 {len(res.rows):,} 筆')
    for n in res.notes:
        print(f'  {n}')

    out_dir = args.輸出 or os.path.dirname(docx[0])
    stem = os.path.splitext(os.path.basename(docx[0]))[0]
    out = os.path.join(out_dir, f'{stem}_排版比對_{datetime.now():%Y%m%d-%H%M}.xlsx')
    report.write(out, doc, {'比對': res}, extra=[('排版稿', os.path.basename(pdf[0]))])
    print(f'  報表：{out}（{time.time() - t0:.1f} 秒）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
