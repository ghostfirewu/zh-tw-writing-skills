#!/usr/bin/env python3
"""繁中守門：掃文字檔裡的簡體殘留、一簡多繁、錯轉繁與中國用語。只用 Python 標準函式庫。

用法：
    python3 zhtw_check.py 檔案.md [檔案2.txt ...]     # 掃檔案
    echo "这里的视频" | python3 zhtw_check.py -        # 掃標準輸入
選項：
    --only 簡體,錯轉                  只跑指定類別，逗號分隔（簡體／一簡多繁／錯轉／用語；預設全跑）
    --level A                         用語只報 A 級（安全直換）；預設 A、B 都報
    --json                            輸出 JSON（給程式或 AI 讀）
    --config-dir 資料夾                指定專案設定資料夾（預設自動找 .zh-tw-writing/，見下）
    --no-config                       不讀專案設定
結束代碼：有「簡體／一簡多繁／錯轉／A 級用語」命中＝1；只有 B 級（看語境）或沒命中＝0；用法錯誤＝2。

本工具只列「候選」，不改檔。B 級用語要看語境判斷（例：「程序」在「申請程序」裡是台灣正常用法）。
Markdown 的程式碼區塊（``` 圍起來的段落與 `行內程式碼`）不查用語，但仍查簡體字。

專案設定（不改本工具也能個人化）：在專案裡放一個 .zh-tw-writing/ 資料夾——
    terms.tsv   追加或覆寫中國用語，格式同 data/terms.tsv
    allow.txt   白名單，一行一個詞；命中落在這些詞裡就不報（專名、地名、引文）
找資料夾的順序：--config-dir → 環境變數 ZHTW_WRITING_DIR → $CLAUDE_PROJECT_DIR/.zh-tw-writing → 目前目錄/.zh-tw-writing
"""
import argparse
import json
import os
import re
import sys
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), 'data')

CATEGORIES = ('簡體', '一簡多繁', '錯轉', '用語')


def is_cjk(ch):
    o = ord(ch)
    return 0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF or 0x20000 <= o <= 0x2EBEF


@lru_cache(None)
def gb_only_chars():
    """GB2312 一、二級漢字中，標準 Big5（常用＋次常用字）沒收的字＝簡體字候選。"""
    gb = set()
    for b1 in range(0xB0, 0xF8):
        for b2 in range(0xA1, 0xFF):
            try:
                gb.add(bytes([b1, b2]).decode('gb2312'))
            except UnicodeDecodeError:
                pass
    big5 = set()
    for b1 in range(0xA4, 0xFA):
        for b2 in list(range(0x40, 0x7F)) + list(range(0xA1, 0xFF)):
            code = (b1 << 8) | b2
            if not (0xA440 <= code <= 0xC67E or 0xC940 <= code <= 0xF9D5):
                continue
            try:
                big5.add(bytes([b1, b2]).decode('big5'))
            except UnicodeDecodeError:
                pass
    return frozenset(c for c in gb - big5 if is_cjk(c))


@lru_cache(None)
def taiwan_chars():
    """data/台灣正字.txt：標準 Big5 沒收、但台灣正式使用的字（酶、肽……），不算簡體。"""
    return frozenset(ln.split('\t')[0].strip() for ln in read_list('台灣正字.txt') if ln.strip())


@lru_cache(None)
def simplified_chars():
    """簡體字候選：GB2312 有、Big5 無，扣掉台灣正字。"""
    return gb_only_chars() - taiwan_chars()


def read_list(name):
    path = os.path.join(DATA, name)
    with open(path, encoding='utf-8-sig') as f:
        return [ln.rstrip('\r\n') for ln in f if ln.strip() and not ln.startswith(("'", '#'))]


@lru_cache(None)
def one_to_many():
    """{字: (可疑二字組集合, 排除詞清單)}，格式見 data/一簡多繁.txt 檔頭。"""
    table = {}
    for ln in read_list('一簡多繁.txt'):
        f = ln.split(',')
        sus = {w for w in f[1].split('|') if w} if len(f) > 1 else set()
        exc = [w for w in f[2].split('|') if w] if len(f) > 2 else []
        table[f[0]] = (sus, exc)
    return table


@lru_cache(None)
def misconversions():
    return tuple(read_list('錯轉.txt'))


def parse_terms(lines):
    rows = []
    for ln in lines:
        f = ln.split('\t') + [''] * 5
        word, sug, level = f[0].strip(), f[1].strip(), f[2].strip().upper()
        if not word or level not in ('A', 'B'):
            continue   # 格式不對的列略過，不讓整支工具掛掉
        exc = [w for w in f[3].split('|') if w.strip()]
        rows.append((word, sug, level, exc, f[4].strip()))
    return rows


@lru_cache(None)
def terms():
    """內建用語表：[(詞, 建議, 級別, 排除詞, 說明)]，依詞長由長到短排序（先比長詞）。"""
    rows = parse_terms(read_list('terms.tsv'))
    rows.sort(key=lambda r: -len(r[0]))
    return rows


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


def _read_user_list(path):
    if not os.path.isfile(path):
        return []
    with open(path, encoding='utf-8-sig', errors='replace') as f:
        return [ln.rstrip('\r\n') for ln in f if ln.strip() and not ln.startswith(("'", '#'))]


def load_config(config_dir):
    """讀專案設定：{'dir', 'terms'（追加的用語列）, 'allow'（白名單詞）}。"""
    if not config_dir:
        return None
    return {'dir': config_dir,
            'terms': parse_terms(_read_user_list(os.path.join(config_dir, 'terms.tsv'))),
            'allow': [w.strip() for w in _read_user_list(os.path.join(config_dir, 'allow.txt')) if w.strip()]}


def merged_terms(config):
    if not config or not config['terms']:
        return terms()
    extra = {r[0]: r for r in config['terms']}
    rows = [r for r in terms() if r[0] not in extra] + list(extra.values())
    rows.sort(key=lambda r: -len(r[0]))
    return rows


def covered(text, start, end, words):
    """text[start:end] 是否落在 words 任一詞的某次出現之內。"""
    for w in words:
        i = text.find(w, max(0, start - len(w) + 1))
        while i >= 0 and i <= start:
            if i + len(w) >= end:
                return True
            i = text.find(w, i + 1)
    return False


def code_mask(lines):
    """回傳每行的「程式碼」遮罩（True＝該字元在程式碼內）。處理 ``` 區塊與 `行內`。"""
    masks, fenced = [], False
    for line in lines:
        if line.lstrip().startswith(('```', '~~~')):
            masks.append([True] * len(line))
            fenced = not fenced
            continue
        if fenced:
            masks.append([True] * len(line))
            continue
        m = [False] * len(line)
        for mt in re.finditer(r'`[^`\n]+`', line):
            for k in range(mt.start(), mt.end()):
                m[k] = True
        masks.append(m)
    return masks


def check_text(text, only=CATEGORIES, level=('A', 'B'), config=None, stats=None):
    """回傳命中清單；每筆是 dict：line、col（從 1 起）、category、match、suggestion、level、note。
    config＝load_config() 的結果；stats 若給 dict，會填入 'allowed'（被白名單略過的筆數）。"""
    hits = []
    lines = text.split('\n')
    masks = code_mask(lines) if '用語' in only else None
    gb_only = simplified_chars()
    otm = one_to_many()
    allow = config['allow'] if config else []
    n_allowed = 0
    for ln_no, line in enumerate(lines, 1):
        def add(cat, s, e, sug='', lv='', note=''):
            hits.append({'line': ln_no, 'col': s + 1, 'category': cat, 'match': line[s:e],
                         'suggestion': sug, 'level': lv, 'note': note})

        if '簡體' in only:
            for i, ch in enumerate(line):
                if ch in gb_only:
                    add('簡體', i, i + 1, note='GB2312 有、Big5 無的字；地名、日本人名可能誤報')

        if '一簡多繁' in only:
            for i, ch in enumerate(line):
                if ch not in otm:
                    continue
                sus, exc = otm[ch]
                if covered(line, i, i + 1, exc):
                    continue
                for a, b in ((i - 1, i + 1), (i, i + 2)):
                    if a >= 0 and b <= len(line) and line[a:b] in sus:
                        add('一簡多繁', a, b, note='疑似簡體殘留（簡體形本身也是正體字，轉換器沒轉）')

        if '錯轉' in only:
            for w in misconversions():
                i = line.find(w)
                while i >= 0:
                    add('錯轉', i, i + len(w), note='轉換器選錯繁體；跨詞界時為誤報（例：頭＋發燙）')
                    i = line.find(w, i + 1)

        if '用語' in only:
            mask = masks[ln_no - 1]
            taken = [False] * len(line)
            for word, sug, lv, exc, note in merged_terms(config):
                i = line.find(word)
                while i >= 0:
                    j = i + len(word)
                    if allow and not any(taken[i:j]) and covered(line, i, j, allow):
                        if lv in level and not any(mask[i:j]):
                            n_allowed += 1   # 白名單：不報、也不占位；只計原本會報的
                    elif not any(taken[i:j]) and not any(mask[i:j]):
                        for k in range(i, j):
                            taken[k] = True   # 長詞先占位，短詞不重複報
                        if lv in level and not covered(line, i, j, exc):
                            add('用語', i, j, sug, lv, note)
                    i = line.find(word, i + 1)
    if allow:
        kept = [h for h in hits
                if not covered(lines[h['line'] - 1], h['col'] - 1, h['col'] - 1 + len(h['match']), allow)]
        n_allowed += len(hits) - len(kept)
        hits = kept
    if stats is not None and allow:
        stats['allowed'] = stats.get('allowed', 0) + n_allowed
    # 同一處只留一筆（簡體字可能同時被一簡多繁、用語抓到時各自保留，類別不同）
    seen, out = set(), []
    for h in sorted(hits, key=lambda h: (h['line'], h['col'], h['category'])):
        key = (h['line'], h['col'], h['category'], h['match'])
        if key not in seen:
            seen.add(key)
            out.append(h)
    return out


def is_blocking(h):
    return h['category'] != '用語' or h['level'] == 'A'


def fmt(path, h):
    s = f"{path}:{h['line']}:{h['col']}  [{h['category']}{h['level'] and ' ' + h['level']}] {h['match']}"
    if h['suggestion']:
        s += f" → {h['suggestion']}"
    if h['note']:
        s += f"　— {h['note']}"
    return s


def parse_only(value):
    cats = [c.strip() for c in re.split(r'[,，、]', value) if c.strip()]
    bad = [c for c in cats if c not in CATEGORIES]
    if bad or not cats:
        raise argparse.ArgumentTypeError(f'類別只能是 {"、".join(CATEGORIES)}（收到：{value}）')
    return cats


def main(argv=None):
    ap = argparse.ArgumentParser(description='繁中守門：簡體殘留、一簡多繁、錯轉繁、中國用語')
    ap.add_argument('files', nargs='*', default=['-'])
    ap.add_argument('--only', type=parse_only, default=list(CATEGORIES),
                    help='只跑指定類別，逗號分隔：' + ','.join(CATEGORIES))
    ap.add_argument('--level', choices=('A', 'B', 'all'), default='all')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--config-dir', help='專案設定資料夾（預設自動找 .zh-tw-writing/）')
    ap.add_argument('--no-config', action='store_true', help='不讀專案設定')
    args = ap.parse_args(argv)
    level = ('A', 'B') if args.level == 'all' else (args.level,)
    if args.config_dir and not os.path.isdir(args.config_dir):
        print(f'找不到設定資料夾：{args.config_dir}', file=sys.stderr)
        return 2
    config = None if args.no_config else load_config(find_config_dir(args.config_dir))
    stats = {}
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            pass

    results, blocking = {}, False
    for path in args.files:
        if path == '-':
            text = sys.stdin.buffer.read().decode('utf-8', errors='replace')
            name = '<stdin>'
        else:
            try:
                with open(path, encoding='utf-8-sig', errors='replace') as f:
                    text = f.read()
            except OSError as e:
                print(f'讀不到 {path}：{e}', file=sys.stderr)
                return 2
            name = path
        hits = check_text(text, tuple(args.only), level, config=config, stats=stats)
        results[name] = hits
        blocking = blocking or any(is_blocking(h) for h in hits)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=1))
    else:
        total = 0
        for name, hits in results.items():
            for h in hits:
                print(fmt(name, h))
            total += len(hits)
        if config:
            print(f"套用專案設定 {config['dir']}：追加 {len(config['terms'])} 條用語、"
                  f"白名單 {len(config['allow'])} 條（本次略過 {stats.get('allowed', 0)} 筆）")
        print(f'共 {total} 筆候選' + ('（含需處理項，結束代碼 1）' if blocking else ''))
    return 1 if blocking else 0


if __name__ == '__main__':
    sys.exit(main())
