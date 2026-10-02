"""讀排版 PDF 的文字層，分成三股：正文、隨頁註腳、頁首頁尾。

- 行：把字依垂直位置分行、行內依水平位置排序（只支援橫排）。
- 頁首頁尾：落在頁面上下邊界帶內的行（比例見設定），另外保存供報表抽查。
- 隨頁註腳：頁面最後一行正文字級之後、字級明顯較小的行。
- 注碼：正文裡字級明顯較小的數字與 *†‡（上標注碼），原稿裡是 Word 的註腳參照、沒有文字，故移除並計數。
- 行末連字號不接回（分不出是斷字還是 meta-governor 這類真連字號），記下行尾位置，比對時再判斷。
"""
import re
from collections import Counter
from dataclasses import dataclass, field

import pdfplumber

LIGATURES = {'ﬀ': 'ff', 'ﬁ': 'fi', 'ﬂ': 'fl', 'ﬃ': 'ffi', 'ﬄ': 'ffl', 'ﬅ': 'st', 'ﬆ': 'st'}
DROP = set(' \t\r\n\u00a0\u3000\u00ad\u200b\u200c\u200d\u2060\ufeff')
MARK_CHARS = set('0123456789*†‡§¹²³⁴⁵⁶⁷⁸⁹⁰')


@dataclass
class Stream:
    text: str = ''
    pages: list = field(default_factory=list)   # 每個字所在的 PDF 頁（1 起算）
    line_ends: set = field(default_factory=set)  # 每一行最後一個字的位置

    def add(self, s, page):
        self.text += s
        self.pages.extend([page] * len(s))


@dataclass
class PdfText:
    main: Stream
    notes: Stream
    hf_lines: list        # (頁, 文字)
    printed: dict         # PDF 頁 -> 書上印的頁碼（從頁尾頁首抓，抓不到就沒有）
    toc_pages: set        # 看起來是目次的頁（3 行以上以點線引線接頁碼結尾）
    marks_dropped: int
    body_size: float
    n_pages: int


def normalize(s):
    """比對用正規化：去空白與看不見的字元、拆連字。回傳 (新字串, 每個字對應原字串的位置)。"""
    out, idx = [], []
    for i, ch in enumerate(s):
        if ch in DROP:
            continue
        rep = LIGATURES.get(ch, ch)
        out.append(rep)
        idx.extend([i] * len(rep))
    return ''.join(out), idx


def _lines(chars):
    chars = [c for c in chars if c['text'].strip() or c['text'] == chr(0x3000)]
    chars.sort(key=lambda c: (round(c['top'], 1), c['x0']))
    lines = []
    for c in chars:
        if lines:
            ln = lines[-1]
            tol = 0.5 * max(ln['size'], c['size'])
            if abs(c['top'] - ln['top']) <= tol or (c['top'] < ln['bottom'] and c['bottom'] > ln['top'] + tol * 0.2
                                                  and abs(c['bottom'] - ln['bottom']) <= tol):
                ln['chars'].append(c)
                ln['bottom'] = max(ln['bottom'], c['bottom'])
                continue
        lines.append({'top': c['top'], 'bottom': c['bottom'], 'size': c['size'], 'chars': [c]})
    for ln in lines:
        ln['chars'].sort(key=lambda c: c['x0'])
        sizes = sorted(c['size'] for c in ln['chars'])
        ln['size'] = sizes[len(sizes) // 2]
        ln['text'] = ''.join(c['text'] for c in ln['chars'])
    lines.sort(key=lambda ln: ln['top'])
    return lines


def _hf_key(ln):
    t = re.sub(r'\s', '', ln['text'])
    t = re.sub(r'\d+', '#', t)
    if re.fullmatch(r'[ivxlcdm]{1,6}', t, re.I):
        t = '#'
    return round(ln['top'] / 3), t


def load(path, cfg):
    sec = cfg['排版比對']
    top_ratio = sec.getfloat('頁首範圍', 0.07)
    bottom_ratio = sec.getfloat('頁尾範圍', 0.07)
    note_ratio = sec.getfloat('註腳字級比', 0.92)
    mark_ratio = sec.getfloat('注碼字級比', 0.8)

    with pdfplumber.open(path) as pdf:
        pages = [(p.height, _lines(p.chars)) for p in pdf.pages]
    sizes = Counter()
    for _, lines in pages:
        for ln in lines:
            for c in ln['chars']:
                sizes[round(c['size'], 1)] += 1
    body = sizes.most_common(1)[0][0] if sizes else 10.0

    # 上下 15% 內、同一高度在 3 頁以上出現相同文字（數字視為相同）的行＝頁首頁尾（書眉、頁碼）
    zone = 0.15
    seen = Counter()
    for height, lines in pages:
        for ln in lines:
            if ln['top'] < height * zone or ln['bottom'] > height * (1 - zone):
                seen[_hf_key(ln)] += 1
    repeat = max(3, len(pages) // 10)

    leader = re.compile(r'([.．…·‧]{3,}|…{2,})\s*\d{1,4}$')
    toc = {pno for pno, (_, lines) in enumerate(pages, 1) if sum(1 for ln in lines if leader.search(ln['text'].strip())) >= 3}

    main, notes = Stream(), Stream()
    hf, printed, marks = [], {}, 0
    for pno, (height, lines) in enumerate(pages, 1):
        body_lines, rest = [], []
        for ln in lines:
            in_zone = ln['top'] < height * zone or ln['bottom'] > height * (1 - zone)
            if ln['top'] < height * top_ratio or ln['bottom'] > height * (1 - bottom_ratio) or                (in_zone and seen[_hf_key(ln)] >= repeat):
                hf.append((pno, ln['text'].strip()))
                t = re.sub(r'\s', '', ln['text'])
                # 頁碼可能單獨一行，也可能和書名、章名印在同一行的開頭或結尾（「12書名」「第1章　標題　13」）
                m = re.fullmatch(r'\d{1,4}|[ivxlcdm]{1,6}', t, re.I) or re.match(r'(\d{1,4})(?!\d)(?=\D)', t)                     or re.search(r'(?<=\D)(?<!第)(\d{1,4})$', t)
                if m and pno not in printed:
                    printed[pno] = m.group(1) if m.groups() else m.group()
            else:
                rest.append(ln)
        # 最後一行正文字級之後、字級較小的行＝隨頁註腳
        last_body = max((i for i, ln in enumerate(rest) if ln['size'] >= body * note_ratio), default=-1)
        for i, ln in enumerate(rest):
            is_note = i > last_body and ln['size'] < body * note_ratio
            body_lines.append((ln, is_note))

        for ln, is_note in body_lines:
            target = notes if is_note else main
            text = ''
            for c in ln['chars']:
                ch = c['text']
                if not is_note and ch in MARK_CHARS and c['size'] < body * mark_ratio:
                    marks += 1
                    continue
                text += ch
            text = ''.join(LIGATURES.get(ch, ch) for ch in text if ch not in DROP)
            if not text:
                continue
            target.add(text, pno)
            target.line_ends.add(len(target.text) - 1)
    return PdfText(main, notes, hf, printed, toc, marks, body, len(pages))
