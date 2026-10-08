#!/usr/bin/env python3
"""風格檔萃取：從使用者自己寫的文章或貼文，算出可量化的寫作習慣，存成 voice.json。只用 Python 標準函式庫。

用法：
    python3 voice_profile.py 貼文1.md 貼文2.md ...
    python3 voice_profile.py --split 討論串匯出.md          # 單一檔案裡用單獨一行的 --- 分篇
    python3 voice_profile.py --phrase 說真的 --phrase 老實說 *.md
    python3 voice_profile.py --out .zh-tw-writing/voice.json *.md
選項：
    --json      輸出 JSON（不加 --out 時印到標準輸出）
    --out       寫出 voice.json（只存統計值與檔名，不存原文）
    --phrase    要計算頻率的口頭禪，可重複
    --split     以單獨一行的 --- 分篇
結束代碼：成功＝0，用法錯誤或讀不到檔案＝2。

算的東西：句長與段落長、每千字的語氣詞／驚嘆號／問號／刪節號／破折號／波浪號／emoji／英文詞、
自稱方式、指定口頭禪的頻率。幽默、立場、比喻這些質性特徵算不出來，由 agent 讀樣本後寫進 voice.md。

裝了 zh-tw-anti-slop 時，會順便算每篇樣本的 AI 腔密度，偏高的標「疑似AI腔」：
那篇可能有 AI 代筆，學進去會把 AI 腔當成個人風格。只標不刪，要不要排除由人決定。
"""
import argparse
import importlib.util
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SLOP_SCAN = os.path.join(HERE, '..', '..', 'zh-tw-anti-slop', 'scripts', 'slop_scan.py')

MIN_CHARS, MIN_DOCS = 3000, 5          # 低於此，統計多半是雜訊，信心標「低」
DEFAULT_LONG = 80                       # 沒有風格檔時的長句上限

# 口語語氣詞：後面不接漢字才算（排除吧台、耶穌、好啦好啦的第一個）；「欸」幾乎只當感嘆詞，出現就算
PARTICLE = re.compile(r'欸|(?<![酒網貼])(?:啦|吧|耶|喔|嘛|齁|啊|哦|囉|唷|咧)(?![一-鿿])')
PUNCT = {
    '驚嘆號': re.compile(r'[！!]'),
    '問號': re.compile(r'[？?]'),
    '刪節號': re.compile(r'…+|\.{3,}'),
    '破折號': re.compile(r'—+|─{2,}'),
    '波浪號': re.compile(r'～+|~+'),
}
EMOJI = re.compile('[\U0001F300-\U0001FAFF☀-➿]')
LATIN = re.compile(r'[A-Za-z][A-Za-z0-9_.+#/-]*[A-Za-z0-9]|[A-Za-z]')
SELF = {'我': r'我(?!們)', '我們': r'我們', '筆者': r'筆者', '本人': r'本人', '小編': r'小編'}
SENT_END = re.compile(r'[。！？!?；\n]+')


def strip_code(text):
    text = re.sub(r'(?ms)^\s*(```|~~~).*?^\s*\1[^\n]*$', ' ', text)
    return re.sub(r'`[^`\n]+`', ' ', text)


def clean(text):
    return strip_code(text).replace('**', '').replace('__', '')


def char_count(text):
    return sum(1 for ch in text if not ch.isspace())


def counts(text):
    """回傳各項特徵的出現次數（程式碼不計）。"""
    t = clean(text)
    c = {'語氣詞': len(PARTICLE.findall(t))}
    for k, rx in PUNCT.items():
        c[k] = len(rx.findall(t))
    c['emoji'] = len(EMOJI.findall(t))
    c['英文詞'] = len(LATIN.findall(t))
    return c


def sentences(text):
    """斷句後的句子（去掉空白，不含句末標點）。"""
    out = []
    for s in SENT_END.split(clean(text)):
        s = ''.join(s.split())
        if s:
            out.append(s)
    return out


def paragraphs(text):
    return [p for p in re.split(r'\n\s*\n', clean(text)) if p.strip()]


def per_k(n, chars):
    return round(n * 1000 / chars, 2) if chars else 0.0


def _quartiles(xs):
    if not xs:
        return {'p25': 0, '中位數': 0, 'p75': 0}
    if len(xs) == 1:
        return {'p25': xs[0], '中位數': xs[0], 'p75': xs[0]}
    q = statistics.quantiles(xs, n=4)
    return {'p25': round(q[0], 1), '中位數': round(statistics.median(xs), 1), 'p75': round(q[2], 1)}


_slop = None


def slop_available():
    global _slop
    if _slop is None:
        _slop = False
        if os.path.isfile(SLOP_SCAN):
            spec = importlib.util.spec_from_file_location('slop_scan', SLOP_SCAN)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _slop = mod
    return bool(_slop)


def slop_density(text):
    if not slop_available():
        return None, False
    hits = [h for h in _slop.scan(text) if not h['category'].startswith('Markdown')]
    dens = per_k(len(hits), char_count(clean(text)))
    return dens, len(hits) >= 2 and dens >= 2


def build(texts, names=None, phrases=None):
    """texts：每篇樣本的全文；names：對應的檔名（只存檔名，不存路徑）。"""
    names = names or [f'樣本{i + 1}' for i in range(len(texts))]
    total = {k: 0 for k in ['語氣詞'] + list(PUNCT) + ['emoji', '英文詞']}
    parts, sent_lens, para_lens, detail = {}, [], [], []
    selfc = {k: 0 for k in SELF}
    phr = {p: 0 for p in (phrases or [])}
    chars = 0
    for text, name in zip(texts, names):
        n = char_count(clean(text))
        chars += n
        for k, v in counts(text).items():
            total[k] += v
        t = clean(text)
        for m in PARTICLE.finditer(t):
            parts[m.group()] = parts.get(m.group(), 0) + 1
        for k, pat in SELF.items():
            selfc[k] += len(re.findall(pat, t))
        for p in phr:
            phr[p] += t.count(p)
        sent_lens += [len(s) for s in sentences(text)]
        para_lens += [char_count(p) for p in paragraphs(text)]
        dens, sus = slop_density(text)
        detail.append({'檔名': os.path.basename(name), '字數': n, 'AI腔每千字': dens, '疑似AI腔': sus})
    q = _quartiles(sent_lens)
    return {
        '版本': 1,
        '樣本': {'篇數': len(texts), '字數': chars,
                 '信心': '足夠' if chars >= MIN_CHARS and len(texts) >= MIN_DOCS else '低'},
        '句長': q,
        '段落長': {'中位數': round(statistics.median(para_lens), 1) if para_lens else 0},
        '每千字': {k: per_k(v, chars) for k, v in total.items()},
        '語氣詞': {k: per_k(v, chars) for k, v in sorted(parts.items(), key=lambda x: -x[1])},
        '自稱': {k: v for k, v in selfc.items() if v},
        '口頭禪': {k: per_k(v, chars) for k, v in phr.items()},
        '長句上限': int(min(120, max(60, round(q['p75'] * 2)))),
        '樣本明細': detail,
    }


def split_docs(text):
    return [d for d in re.split(r'(?m)^---[ \t]*$', text) if d.strip()]


def render(prof):
    s = prof['樣本']
    lines = [f"樣本：{s['篇數']} 篇、{s['字數']} 字，信心{s['信心']}"
             + ('' if s['信心'] == '足夠' else f'（建議至少 {MIN_DOCS} 篇、{MIN_CHARS} 字；目前的數字只當參考）')]
    q = prof['句長']
    lines.append(f"句長：中位數 {q['中位數']} 字（p25 {q['p25']}、p75 {q['p75']}）；段落中位數 {prof['段落長']['中位數']} 字；"
                 f"長句上限 {prof['長句上限']} 字")
    lines.append('每千字：' + '、'.join(f'{k} {v}' for k, v in prof['每千字'].items()))
    if prof['語氣詞']:
        lines.append('語氣詞（每千字）：' + '、'.join(f'{k} {v}' for k, v in prof['語氣詞'].items()))
    if prof['自稱']:
        lines.append('自稱（次數）：' + '、'.join(f'{k} {v}' for k, v in prof['自稱'].items()))
    if prof['口頭禪']:
        lines.append('口頭禪（每千字）：' + '、'.join(f'{k} {v}' for k, v in prof['口頭禪'].items()))
    sus = [d['檔名'] for d in prof['樣本明細'] if d['疑似AI腔']]
    if sus:
        lines.append('⚠️ 疑似AI腔（AI 腔密度偏高，可能有 AI 代筆；考慮排除後重算）：' + '、'.join(sus))
    elif not slop_available():
        lines.append('（找不到 zh-tw-anti-slop，沒有檢查樣本的 AI 腔密度）')
    return '\n'.join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description='從自己的文章萃取可量化的寫作習慣（繁體中文）')
    ap.add_argument('files', nargs='+')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--out', help='寫出 voice.json 的路徑')
    ap.add_argument('--phrase', action='append', default=[], help='要計算頻率的口頭禪，可重複')
    ap.add_argument('--split', action='store_true', help='以單獨一行的 --- 分篇')
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        pass
    texts, names = [], []
    for path in args.files:
        try:
            if path == '-':
                raw = sys.stdin.buffer.read().decode('utf-8', errors='replace')
            else:
                with open(path, encoding='utf-8-sig', errors='replace') as f:
                    raw = f.read()
        except OSError as e:
            print(f'讀不到 {path}：{e}', file=sys.stderr)
            return 2
        docs = split_docs(raw) if args.split else [raw]
        name = '<stdin>' if path == '-' else os.path.basename(path)
        for i, d in enumerate(docs, 1):
            texts.append(d)
            names.append(f'{name}#{i}' if len(docs) > 1 else name)
    prof = build(texts, names=names, phrases=args.phrase)
    if args.out:
        try:
            with open(args.out, 'w', encoding='utf-8') as f:
                json.dump(prof, f, ensure_ascii=False, indent=1)
        except OSError as e:
            print(f'寫不出 {args.out}：{e}', file=sys.stderr)
            return 2
    if args.json and not args.out:
        print(json.dumps(prof, ensure_ascii=False, indent=1))
    else:
        print(render(prof))
        if args.out:
            print(f'已寫出 {args.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
