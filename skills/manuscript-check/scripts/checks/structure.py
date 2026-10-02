"""④ 結構：標題編號跳號／重號、圖表編號連續性、圖表編號與內文引用互相對應。

標題靠 Word 的標題樣式（或大綱階層）辨識；作者沒用標題樣式時，標題檢查無法執行。
"""
import re

from .common import Hit, Result

CN_DIGIT = {'〇': 0, '零': 0, '一': 1, '二': 2, '兩': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}
FW = str.maketrans('０１２３４５６７８９．', '0123456789.')


def cn2int(s):
    s = s.translate(FW)
    if s.isdigit():
        return int(s)
    total, cur = 0, 0
    for ch in s:
        if ch in CN_DIGIT:
            cur = CN_DIGIT[ch]
        elif ch == '十':
            total += (cur or 1) * 10
            cur = 0
        elif ch == '百':
            total += (cur or 1) * 100
            cur = 0
        else:
            return None
    return total + cur


H_ORDINAL = re.compile(r'^\s*第\s*([0-9０-９〇零一二兩三四五六七八九十百]+)\s*[章節篇部回講卷]')
H_DOTTED = re.compile(r'^\s*([0-9０-９]+(?:[.．][0-9０-９]+)*)(?![0-9０-９])')
H_CNLIST = re.compile(r'^\s*([一二三四五六七八九十]+)\s*[、．.]')


def heading_number(text):
    """回傳 (顯示用字串, 數字序列)；沒有編號回傳 None。"""
    m = H_ORDINAL.match(text)
    if m:
        n = cn2int(m.group(1))
        return (m.group(0).strip(), (n,)) if n is not None else None
    m = H_DOTTED.match(text)
    if m:
        s = m.group(1).translate(FW)
        return s, tuple(int(x) for x in s.split('.'))
    m = H_CNLIST.match(text)
    if m:
        n = cn2int(m.group(1))
        return (m.group(1), (n,)) if n is not None else None
    return None


LABEL = r'(圖|表|Figure|Fig\.|Table)\s*([0-9０-９]+(?:\s*[-‑–—.．]\s*[0-9０-９]+)?)'
CAPTION = re.compile(r'^\s*' + LABEL)
REF = re.compile(LABEL)
KIND = {'圖': '圖', '表': '表', 'Figure': 'Figure', 'Fig.': 'Figure', 'Table': 'Table'}


def fig_key(kind, num):
    parts = re.split(r'\s*[-‑–—.．]\s*', num.translate(FW))
    return KIND[kind], tuple(int(x) for x in parts)


def fig_label(key):
    kind, nums = key
    return kind + '-'.join(map(str, nums))


def _is_caption(p):
    s = p.style.lower()
    return any(k in s for k in ('caption', '標號', '圖說', '表說', '題注')) or len(p.text.strip()) <= 60


def _check_headings(doc, res):
    heads = [p for p in doc.body if p.level]
    if not heads:
        res.notes.append('未偵測到標題樣式，章節編號檢查未執行')
        return
    auto = sum(1 for p in heads if p.auto_num)
    if auto:
        res.notes.append(f'{auto} 個標題使用 Word 自動編號，編號不在文字裡，這些標題不檢查跳號')
    last = {}           # 各層級目前的上一個編號
    chapter_no = None   # 目前所屬一級標題的編號
    for p in heads:
        num = heading_number(p.text)
        # 上層出現新標題時，下層重新起算
        for k in [k for k in last if k > p.level]:
            del last[k]
        if num is None:
            continue
        label, seq = num
        if p.level == 1:
            chapter_no = seq[0]
        cur = seq[-1]
        prev = last.get(p.level)
        if prev is not None:
            if cur == prev:
                res.hits.append(Hit('標題重號', p, label, 0, len(label), f'與上一個同層標題編號相同（{prev}）'))
            elif cur != prev + 1:
                res.hits.append(Hit('標題跳號', p, label, 0, len(label), f'上一個同層標題是 {prev}，這裡是 {cur}'))
        elif p.level > 1 and cur != 1:
            res.hits.append(Hit('標題跳號', p, label, 0, len(label), f'本層第一個標題從 {cur} 開始'))
        if p.level > 1 and len(seq) > 1 and chapter_no is not None and seq[0] != chapter_no:
            res.hits.append(Hit('編號與所屬章不符', p, label, 0, len(label), f'所屬章的編號是 {chapter_no}'))
        last[p.level] = cur


def _check_figures(doc, res):
    captions = {}   # key -> (para, start, end)
    refs = {}       # key -> [(para, start, end)]
    order = []
    for p in doc.paras:
        cm = CAPTION.match(p.text) if p.part == '內文' and _is_caption(p) else None
        if cm:
            key = fig_key(cm.group(1), cm.group(2))
            if key in captions:
                res.hits.append(Hit('圖表重號', p, fig_label(key), cm.start(1), cm.end(2), '同一個編號出現兩次圖說'))
            else:
                captions[key] = (p, cm.start(1), cm.end(2))
                order.append(key)
        for m in REF.finditer(p.text):
            if cm and m.start() == cm.start(1):
                continue
            refs.setdefault(fig_key(m.group(1), m.group(2)), []).append((p, m.start(), m.end()))

    # 連續性：同一種類、同一個章前綴內，最後一位數要逐一遞增
    last = {}
    for key in order:
        kind, nums = key
        group = (kind, nums[:-1])
        prev = last.get(group)
        p, a, b = captions[key]
        if prev is None and nums[-1] != 1:
            res.hits.append(Hit('圖表跳號', p, fig_label(key), a, b, f'這一組從 {nums[-1]} 開始'))
        elif prev is not None and nums[-1] != prev + 1:
            res.hits.append(Hit('圖表跳號', p, fig_label(key), a, b, f'上一個是 {fig_label((kind, nums[:-1] + (prev,)))}'))
        last[group] = nums[-1]

    for key, where in refs.items():
        if key not in captions:
            p, a, b = where[0]
            res.hits.append(Hit('引用了但沒有圖說', p, fig_label(key), a, b, f'內文提到 {len(where)} 次，找不到這個編號的圖說'))
    for key in order:
        if key not in refs:
            p, a, b = captions[key]
            res.hits.append(Hit('圖說未被引用', p, fig_label(key), a, b, '內文沒有提到這個編號'))
    if not captions:
        res.notes.append('未偵測到圖說（段首為「圖／表＋編號」的短段落），圖表檢查只列內文引用')


def run(doc, cfg):
    res = Result('④ 結構')
    _check_headings(doc, res)
    _check_figures(doc, res)
    return res
