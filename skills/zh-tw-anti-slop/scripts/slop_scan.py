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
import unicodedata
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


BOLD_ADVICE = ('粗體不會生效，`**` 會原樣顯示。改法依序試：①括號整個包進粗體時，改成只包括號內側'
               '（接著**「設定」**再 → 接著「**設定**」再）；②句末標點包進粗體時，把標點移到外面'
               '（**必須。**詳見 → **必須**。詳見）；③都不行時，在 `**` 的外側加一個半形空格'
               '（接著 **「設定」** 再）；加在內側反而會讓粗體失效')


def _is_punct(ch):
    return unicodedata.category(ch)[0] in 'PS'


def _flanking(prev, nxt):
    """CommonMark 的 left/right-flanking 判定；行首行尾視同空白。"""
    p_ws = prev is None or prev.isspace()
    n_ws = nxt is None or nxt.isspace()
    p_pu = prev is not None and _is_punct(prev)
    n_pu = nxt is not None and _is_punct(nxt)
    left = not n_ws and (not n_pu or p_ws or p_pu)
    right = not p_ws and (not p_pu or n_ws or n_pu)
    return left, right


def bold_issues(line):
    """回傳這一行裡不會生效、且貼著中日韓文字或全形標點的 `**` 位置（0 起算）。只處理恰好兩個星號的符號串。"""
    # 行內程式碼的內容換成字母、保留反引號（反引號本身算標點，會影響判定）
    line = re.sub(r'`[^`\n]+`', lambda m: '`' + 'x' * (len(m.group()) - 2) + '`', line)
    runs = [m for m in re.finditer(r'(?<!\\)\*+', line) if len(m.group()) == 2]
    stack, bad = [], []
    for m in runs:
        s, e = m.span()
        prev, nxt = (line[s - 1] if s else None), (line[e] if e < len(line) else None)
        left, right = _flanking(prev, nxt)
        if right and stack:
            stack.pop()
        elif left:
            stack.append(s)
        else:
            bad.append(s)
    # 只回報貼著中日韓文字或全形標點的 `**`：純英數旁的 `**` 多半是程式碼（x**2、5 ** 2），不是粗體
    return sorted(p for p in bad + stack if _near_cjk(line, p))


def _near_cjk(line, pos):
    return any(0 <= i < len(line) and ord(line[i]) >= 0x2E80 and line[i] != '\n' for i in (pos - 1, pos + 2))


def bold_hits(lines, stripped):
    """以段落（連續的非空白、非程式碼區塊行）為單位配對 `**`，跨行的粗體也能正確配對。"""
    hits, block = [], []

    def flush():
        if not block:
            return
        text = '\n'.join(lines[i] for i in block)
        if '**' in text:
            starts, pos = [], 0
            for i in block:
                starts.append(pos)
                pos += len(lines[i]) + 1
            for off in bold_issues(text):
                k = max(j for j in range(len(block)) if starts[j] <= off)
                no, col = block[k], off - starts[k]
                if stripped[no][col:col + 2] == '**':   # 不在行內程式碼裡
                    hits.append({'line': no + 1, 'col': col + 1, 'match': '**',
                                 'category': 'Markdown・粗體失效', 'advice': BOLD_ADVICE})
        block.clear()

    for i, (orig, st) in enumerate(zip(lines, stripped)):
        if orig.strip() and st.strip():
            block.append(i)
        else:
            flush()
    flush()
    return hits


def scan(text, patterns=None):
    patterns = patterns if patterns is not None else load_patterns()
    hits = []
    lines = text.split('\n')
    stripped = strip_code(lines)
    hits.extend(bold_hits(lines, stripped))
    for no, line in enumerate(stripped, 1):
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
