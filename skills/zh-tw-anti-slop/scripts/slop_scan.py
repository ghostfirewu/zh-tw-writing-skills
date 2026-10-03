#!/usr/bin/env python3
"""AI 腔候選掃描：依 data/slop.tsv 找出常見 AI 腔詞句，列出位置與改寫方向。只用 Python 標準函式庫。

用法：
    python3 slop_scan.py 文案.md [檔案2.txt ...]
    pbpaste | python3 slop_scan.py -
選項：
    --json        輸出 JSON
    --summary     只印各類別筆數
    --config-dir  指定專案設定資料夾（預設自動找 .zh-tw-writing/，見下）
    --no-config   不讀專案設定
結束代碼：有命中＝1，沒命中＝0，用法錯誤＝2。

⚠️ 這是篩選器，不是判官：命中只代表「值得再看一眼」。要不要改，照 SKILL.md 的判準
（刪掉這句，讀者少知道哪個具體事實、立場或情緒？）；字面義（落地窗、指紋解鎖）不算。
句型層的 AI 腔（湊三項排比、同義詞輪替、極短句轟炸）抓不到，立場真空只收固定說法，仍要人工或模型通讀。
Markdown 的程式碼區塊與行內程式碼不掃。

專案設定（不改本工具也能個人化）：在專案裡放一個 .zh-tw-writing/ 資料夾——
    slop.tsv    追加詞條，格式同 data/slop.tsv；樣式相同時以專案設定為準
    allow.txt   白名單，一行一個詞；命中落在這些詞裡就不報（品牌名、專名）
找資料夾的順序：--config-dir → 環境變數 ZHTW_WRITING_DIR → $CLAUDE_PROJECT_DIR/.zh-tw-writing → 目前目錄/.zh-tw-writing
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


def load_patterns(path=DATA, strict=True):
    """讀詞條表。strict=False（專案設定）時，壞掉的列略過，不讓整支工具掛掉。"""
    pats = []
    with open(path, encoding='utf-8-sig', errors='strict' if strict else 'replace') as f:
        for ln in f:
            ln = ln.rstrip('\r\n')
            if not ln.strip() or ln.startswith('#') or (not strict and ln.startswith("'")):
                continue
            cols = ln.split('\t') + ['', '']
            pat, cat, advice = cols[0], cols[1].strip(), cols[2].strip()
            if not strict and (not pat or not cat or '\ufffd' in ln):
                continue   # 專案設定的壞列（缺類別欄、無法解碼）略過
            try:
                rx = re.compile(pat[3:]) if pat.startswith('re:') else re.compile(re.escape(pat))
            except re.error:
                if strict:
                    raise
                continue
            pats.append((rx, cat, advice))
    return pats


CONFIG_NAME = '.zh-tw-writing'


def find_config_dir(explicit=None, cwd=None):
    """找專案設定資料夾；找不到回 None。只看目前目錄，不往上層找。"""
    cands = [explicit, os.environ.get('ZHTW_WRITING_DIR')]
    if os.environ.get('CLAUDE_PROJECT_DIR'):
        cands.append(os.path.join(os.environ['CLAUDE_PROJECT_DIR'], CONFIG_NAME))
    cands.append(os.path.join(cwd or os.getcwd(), CONFIG_NAME))
    for c in cands:
        if c and os.path.isdir(c):
            return c
    return None


def load_config(config_dir):
    """讀專案設定：{'dir', 'patterns'（追加詞條）, 'allow'（白名單詞）}。"""
    if not config_dir:
        return None
    sp, ap = os.path.join(config_dir, 'slop.tsv'), os.path.join(config_dir, 'allow.txt')
    allow = []
    if os.path.isfile(ap):
        with open(ap, encoding='utf-8-sig', errors='replace') as f:
            allow = [ln.strip() for ln in f if ln.strip() and not ln.startswith(("'", '#'))]
    return {'dir': config_dir, 'patterns': load_patterns(sp, strict=False) if os.path.isfile(sp) else [],
            'allow': allow}


def merged_patterns(base, config):
    if not config or not config['patterns']:
        return base
    extra = {rx.pattern: (rx, cat, adv) for rx, cat, adv in config['patterns']}
    return list(extra.values()) + [p for p in base if p[0].pattern not in extra]


def _covered(line, start, end, words):
    for w in words:
        i = line.find(w, max(0, start - len(w) + 1))
        while 0 <= i <= start:
            if i + len(w) >= end:
                return True
            i = line.find(w, i + 1)
    return False


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


def scan(text, patterns=None, config=None, stats=None):
    """config＝load_config() 的結果；stats 若給 dict，會填入 'allowed'（被白名單略過的筆數）。"""
    patterns = merged_patterns(patterns if patterns is not None else load_patterns(), config)
    hits = []
    lines = text.split('\n')
    stripped = strip_code(lines)
    allow = config['allow'] if config else []
    allowed_spans = set()
    hits.extend(bold_hits(lines, stripped))
    for no, line in enumerate(stripped, 1):
        taken = []
        for rx, cat, advice in patterns:
            for m in rx.finditer(line):
                s, e = m.span()
                if s == e or any(s < te and ts < e for ts, te in taken):
                    continue   # 同一段文字只報第一個命中的樣式
                if allow and _covered(lines[no - 1], s, e, allow):
                    allowed_spans.add((no, s, e))   # 白名單：不報、也不占位；同一段只算一次
                    continue
                taken.append((s, e))
                hits.append({'line': no, 'col': s + 1, 'match': lines[no - 1][s:e],
                             'category': cat, 'advice': advice})
    if stats is not None and allow:
        stats['allowed'] = stats.get('allowed', 0) + len(allowed_spans)
    hits.sort(key=lambda h: (h['line'], h['col']))
    return hits


def main(argv=None):
    ap = argparse.ArgumentParser(description='AI 腔候選掃描（繁體中文）')
    ap.add_argument('files', nargs='*', default=['-'])
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--summary', action='store_true')
    ap.add_argument('--config-dir', help='專案設定資料夾（預設自動找 .zh-tw-writing/）')
    ap.add_argument('--no-config', action='store_true', help='不讀專案設定')
    args = ap.parse_args(argv)
    if args.config_dir and not os.path.isdir(args.config_dir):
        print(f'找不到設定資料夾：{args.config_dir}', file=sys.stderr)
        return 2
    config = None if args.no_config else load_config(find_config_dir(args.config_dir))
    stats = {}
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        pass
    patterns = load_patterns()
    results = {}
    for path in args.files:
        if path == '-':
            results['<stdin>'] = scan(sys.stdin.buffer.read().decode('utf-8', errors='replace'), patterns,
                                      config=config, stats=stats)
            continue
        try:
            with open(path, encoding='utf-8-sig', errors='replace') as f:
                results[path] = scan(f.read(), patterns, config=config, stats=stats)
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
        if config:
            print(f"套用專案設定 {config['dir']}：追加 {len(config['patterns'])} 條詞條、"
                  f"白名單 {len(config['allow'])} 條（本次略過 {stats.get('allowed', 0)} 筆）")
        print(f'共 {total} 筆候選')
    else:
        for name, hits in results.items():
            for h in hits:
                print(f"{name}:{h['line']}:{h['col']}  [{h['category']}] {h['match']} → {h['advice']}")
        if config:
            print(f"套用專案設定 {config['dir']}：追加 {len(config['patterns'])} 條詞條、"
                  f"白名單 {len(config['allow'])} 條（本次略過 {stats.get('allowed', 0)} 筆）")
        print(f'共 {total} 筆候選')
    return 1 if total else 0


if __name__ == '__main__':
    sys.exit(main())
