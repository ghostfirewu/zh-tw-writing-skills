"""稿件健檢：對 Word 書稿（.docx）跑規則式檢查，產出 Excel 報表。只讀稿件，不修改。

用法：
    python 稿件健檢.py 書稿.docx [書稿2.docx ...]
    python 稿件健檢.py 書稿.docx --只跑 標點 簡體
    python 稿件健檢.py 書稿.docx --設定 另一份設定.ini --輸出 報表資料夾

也可以把 docx 拖放到「健檢.bat」上。
項目：標點、簡體、罕用字、異形、結構、統計、外文、文獻
"""
import argparse
import os
import sys
import time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from checks import docx_text, foreign, punct, rare, refs, report, simplified, stats, structure, variants  # noqa: E402
from checks.common import load_config  # noqa: E402

CHECKS = {
    '標點': punct,
    '簡體': simplified,
    '罕用字': rare,
    '異形': variants,
    '結構': structure,
    '統計': stats,
    '外文': foreign,
    '文獻': refs,
}


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    ap = argparse.ArgumentParser(description='稿件健檢（規則式，不使用 AI）')
    ap.add_argument('稿件', nargs='+', help='.docx 檔')
    ap.add_argument('--設定', default=os.path.join(HERE, '設定', '設定.ini'))
    ap.add_argument('--只跑', nargs='+', choices=list(CHECKS), help='只跑指定項目')
    ap.add_argument('--輸出', help='報表存放資料夾（預設與稿件同資料夾）')
    args = ap.parse_args()

    cfg = load_config(args.設定)
    names = args.只跑 or list(CHECKS)
    failed = 0
    for path in args.稿件:
        path = os.path.abspath(path)
        print(f'\n■ {os.path.basename(path)}')
        t0 = time.time()
        try:
            doc = docx_text.load(path)
        except Exception as e:
            print(f'  無法讀取：{e}')
            failed += 1
            continue
        print(f'  讀入 {len(doc.body):,} 段、註腳／尾註 {len(doc.paras) - len(doc.body):,} 則')
        results = {}
        for n in names:
            try:
                results[n] = CHECKS[n].run(doc, cfg)
                print(f'  {results[n].title}：{len(results[n].hits):,} 筆')
            except Exception as e:
                print(f'  {n}：執行失敗（{type(e).__name__}: {e}），其他項目照常產出')
                failed += 1
        out_dir = args.輸出 or os.path.dirname(path)
        stem = os.path.splitext(os.path.basename(path))[0]
        out = os.path.join(out_dir, f'{stem}_健檢報表_{datetime.now():%Y%m%d-%H%M}.xlsx')
        report.write(out, doc, results)
        print(f'  報表：{out}（{time.time() - t0:.1f} 秒）')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
