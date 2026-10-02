#!/usr/bin/env python3
"""AI 腔候選掃描：依 data/slop.tsv 找出常見 AI 腔詞句，列出位置與改寫方向。只用 Python 標準函式庫。

用法：
    python3 slop_scan.py 文案.md [檔案2.txt ...]
    pbpaste | python3 slop_scan.py -
選項：
    --json        輸出 JSON
    --summary     只印各類別筆數
結束代碼：有命中＝1，沒命中＝0，用法錯誤＝2。

⚠️ 這是篩選器，不是判官：命中只代表「值得再看一眼」。要不要改，照 SKILL.md 的判準
（刪掉這句，讀者少知道哪個具體事實、立場或情緒？）；字面義（落地窗、指紋解鎖）不算。
句型層的 AI 腔（湊三項排比、同義詞輪替、極短句轟炸）抓不到，立場真空只收固定說法，仍要人工或模型通讀。
Markdown 的程式碼區塊與行內程式碼不掃。
"""
import argparse
import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), 'data', 'slop.tsv')


def load_patterns(path=DATA):
    pats = []
    with open(path, encoding='utf-8-sig') as f:
        for ln in f:
            ln = ln.rstrip('\r\n')
            if not ln.strip() or ln.startswith('#'):
                continue
            cols = ln.split('\t') + ['', '']
            pat, cat, advice = cols[0], cols[1].strip(), cols[2].strip()
            if pat.startswith('re:'):
                rx = re.compile(pat[3:])
            else:
                rx = re.compile(re.escape(pat))
            pats.append((rx, cat, advice))
    return pats


def strip_code(lines):
    """把程式碼區塊與行內程式碼換成等長空白，保留欄位位置。"""
    out, fenced = [], False
    for line in lines:
        if line.lstrip().startswith(('```', '~~~')):
            fenced = not fenced
            out.append(' ' * len(line))
            continue
        if fenced:
            out.append(' ' * len(line))
            continue
        out.append(re.sub(r'`[^`\n]+`', lambda m: ' ' * len(m.group()), line))
    return out


def scan(text, patterns=None):
    patterns = patterns if patterns is not None else load_patterns()
    hits = []
    lines = text.split('\n')
    for no, line in enumerate(strip_code(lines), 1):
        taken = []
        for rx, cat, advice in patterns:
            for m in rx.finditer(line):
                s, e = m.span()
                if s == e or any(s < te and ts < e for ts, te in taken):
                    continue   # 同一段文字只報第一個命中的樣式
                taken.append((s, e))
                hits.append({'line': no, 'col': s + 1, 'match': lines[no - 1][s:e],
                             'category': cat, 'advice': advice})
    hits.sort(key=lambda h: (h['line'], h['col']))
    return hits


def main(argv=None):
    ap = argparse.ArgumentParser(description='AI 腔候選掃描（繁體中文）')
    ap.add_argument('files', nargs='*', default=['-'])
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--summary', action='store_true')
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        pass
    patterns = load_patterns()
    results = {}
    for path in args.files:
        if path == '-':
            results['<stdin>'] = scan(sys.stdin.buffer.read().decode('utf-8', errors='replace'), patterns)
            continue
        try:
            with open(path, encoding='utf-8-sig', errors='replace') as f:
                results[path] = scan(f.read(), patterns)
        except OSError as e:
            print(f'讀不到 {path}：{e}', file=sys.stderr)
            return 2

    total = sum(len(v) for v in results.values())
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=1))
    elif args.summary:
        c = Counter(h['category'] for v in results.values() for h in v)
        for cat, n in c.most_common():
            print(f'{n:4d}  {cat}')
        print(f'共 {total} 筆候選')
    else:
        for name, hits in results.items():
            for h in hits:
                print(f"{name}:{h['line']}:{h['col']}  [{h['category']}] {h['match']} → {h['advice']}")
        print(f'共 {total} 筆候選')
    return 1 if total else 0


if __name__ == '__main__':
    sys.exit(main())
