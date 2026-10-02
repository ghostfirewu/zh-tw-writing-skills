"""⑦ 定稿 docx 與排版 PDF 逐字比對。

作法：
1. 兩邊都去掉空白與看不見的字元再比，換行、字距、斷頁不算差異。
2. 以原稿段落當錨點，依序在 PDF 正文裡找完全相同的位置；找不到的段落與它前後兩個錨點之間的
   PDF 文字做逐字比對，差異就出在這裡。
3. 原稿有、PDF 找不到的文字，若在 PDF 別處完整出現，改判「位置移動」（圖說、框文常被移位）。
4. 註腳另外比：原稿註腳對 PDF 頁面下方的小字級文字。
"""
import re
from collections import Counter
from difflib import SequenceMatcher

from .common import CJK, Hit, Result
from .pdf_text import normalize

MIN_ANCHOR = 6          # 短於此的段落（例：單字標題）不當錨點，避免對到別處
PROBE = 16              # 取每段開頭幾個字當錨點
PUNCT = set('，。、；：？！「」『』（）《》〈〉【】〔〕…—─－,.;:?!()[]"\'“”‘’')


class Side:
    """一邊的文字流，記住每個字屬於哪一段／哪一頁。"""

    def __init__(self, text, owner, offset):
        self.text = text      # 正規化後的字串
        self.owner = owner    # 每個字屬於哪一段（原稿）或哪一頁（PDF）
        self.offset = offset  # 原稿：每個字在原段落中的位置


def docx_side(paras):
    text, owner, offset = [], [], []
    starts = []
    for k, p in enumerate(paras):
        s, idx = normalize(p.text)
        starts.append(len(text))
        text.extend(s)
        owner.extend([k] * len(s))
        offset.extend(idx)
    return Side(''.join(text), owner, offset), starts


def _classify(d, p):
    if d and not p:
        return '疑似漏段' if len(d) >= 30 else '排版稿少了'
    if p and not d:
        if re.fullmatch(r'[0-9*†‡]+', p):
            return '排版稿多了數字（可能是注碼）'
        return '排版稿多了'
    if all(c in PUNCT for c in d + p):
        return '標點不同'
    if re.search(r'\d', d + p):
        return '數字不同'
    return '文字不同'


def _slide(a, b, i1, i2, j1, j2, stops=()):
    """純刪除／純插入的邊界盡量往左移（「第1【5句…第1】6句」→「【第15句…】第16句」），差異才會從完整的字詞開始。"""
    if j1 == j2:        # 原稿有、排版稿沒有
        while i1 > 0 and j1 > 0 and i1 not in stops and a[i1 - 1] == a[i2 - 1] and b[j1 - 1] == a[i1 - 1]:
            i1, i2, j1, j2 = i1 - 1, i2 - 1, j1 - 1, j2 - 1
    elif i1 == i2:      # 排版稿多出來
        while j1 > 0 and i1 > 0 and i1 not in stops and b[j1 - 1] == b[j2 - 1] and a[i1 - 1] == b[j1 - 1]:
            i1, i2, j1, j2 = i1 - 1, i2 - 1, j1 - 1, j2 - 1
    return i1, i2, j1, j2


def _ops(a, b, stops=()):
    """逐字比對，把只隔 1 個相同字的相鄰差異合併成一筆，讀起來比較完整。"""
    ops = [(op[0],) + _slide(a, b, *op[1:], stops=stops) for op in SequenceMatcher(None, a, b, autojunk=False).get_opcodes()
           if op[0] != 'equal']
    merged = []
    for tag, i1, i2, j1, j2 in ops:
        if merged and i1 - merged[-1][1] <= 1 and j1 - merged[-1][3] <= 1:
            merged[-1] = (merged[-1][0], i2, merged[-1][2], j2)
        else:
            merged.append((i1, i2, j1, j2))
    return merged


def _probe(D, st, ln):
    return D[st:st + min(ln, PROBE)]


def _moved(D, P, dstarts, dlens, k, cursor, pos, look=5):
    """第 k 段在 PDF 的位置跳過了一大段；若後面幾段的開頭在 PDF 裡反而出現得比它早，表示第 k 段被移位。"""
    seen = 0
    for j in range(k + 1, len(dstarts)):
        if dlens[j] < MIN_ANCHOR:
            continue
        if P.find(_probe(D, dstarts[j], dlens[j]), cursor, pos) >= 0:
            return True
        seen += 1
        if seen >= look:
            break
    return False


def collate(dside, dstarts, dlens, pside):
    """回傳差異清單 [(原稿起, 原稿迄, PDF 起, PDF 迄)]（都是正規化後字串的位置）。

    每段開頭的 PROBE 個字當錨點；相鄰兩個錨點之間的文字逐字比對。
    段落開頭就有差異、或整段不見的，會併進前一段一起比。
    """
    D, P = dside.text, pside.text
    anchors = [(0, 0)]
    cursor = 0
    for k, (st, ln) in enumerate(zip(dstarts, dlens)):
        if ln < MIN_ANCHOR or st == 0:
            continue
        probe = _probe(D, st, ln)
        gap_d = st - anchors[-1][0]
        pos = P.find(probe, cursor, cursor + gap_d * 2 + 3000)
        if pos < 0:
            continue
        if pos - cursor > gap_d + 50 and _moved(D, P, dstarts, dlens, k, cursor, pos):
            continue    # 這段被移到後面去了（例：圖說），不能當錨點，否則中間全部對不上
        anchors.append((st, pos))
        cursor = pos + 1
    anchors.append((len(D), len(P)))

    starts = set(dstarts)
    diffs = []
    for (d0, p0), (d1, p1) in zip(anchors, anchors[1:]):
        if D[d0:d1] == P[p0:p1]:
            continue
        stops = {x - d0 for x in starts if d0 < x < d1}   # 段落開頭：邊界左移時不跨過
        for i1, i2, j1, j2 in _ops(D[d0:d1], P[p0:p1], stops):
            a, b = d0 + i1, d0 + i2
            if j1 == j2:
                # 純刪除跨了好幾段時依段切開，每段各自判斷（例：被移走的圖說＋被漏排的一段）
                cuts = sorted(x for x in starts if a < x < b)
                for x, y in zip([a] + cuts, cuts + [b]):
                    diffs.append((x, y, p0 + j1, p0 + j2))
            else:
                diffs.append((a, b, p0 + j1, p0 + j2))
    return diffs


def _ctx(s, a, b, w=12):
    x, y = max(0, a - w), min(len(s), b + w)
    return ('…' if x else '') + s[x:a] + '【' + s[a:b] + '】' + s[b:y] + ('…' if y < len(s) else '')


def run(doc, pdf, cfg):
    res = Result('⑦ 排版比對')
    res.header = ['分級', '分類', '章', '原稿位置', 'PDF 頁', '原稿（【】為差異）', '排版稿（【】為差異）', '說明']
    res.rows = []

    def page_label(pno):
        return f'{pno}' + (f'（書頁 {pdf.printed[pno]}）' if pno in pdf.printed else '')

    def emit(level, cat, dside, paras, d0, d1, pside, p0, p1, extra=''):
        k = dside.owner[min(d0, len(dside.owner) - 1)] if dside.owner else None
        para = paras[k] if k is not None else None
        pno = pside.pages[min(p0, len(pside.pages) - 1)] if pside.pages else None
        res.hits.append(Hit(cat, para, dside.text[d0:d1] or pside.text[p0:p1]))
        res.rows.append([level, cat, para.chapter if para else '', para.loc if para else '',
                         page_label(pno) if pno else '',
                         _ctx(dside.text, d0, d1), _ctx(pside.text, p0, p1), extra])

    # --- 正文 ---
    body = [p for p in doc.paras if p.part == '內文']
    dside, dstarts = docx_side(body)
    dlens = [len(normalize(p.text)[0]) for p in body]
    diffs = collate(dside, dstarts, dlens, pdf.main)
    notes = [p for p in doc.paras if p.part != '內文']
    nside, nstarts = docx_side(notes)
    D, P = dside.text, pdf.main.text

    def owner(d0):
        return body[dside.owner[min(d0, len(D) - 1)]] if D else None

    # 表格：原稿逐格讀、排版稿逐行讀，順序天生不同 → 相鄰的表格差異併成一組，只比內容是否相同
    groups, cur = [], None
    for d in diffs:
        in_tab = D and owner(d[0]).in_table
        k = dside.owner[min(d[0], len(D) - 1)] if D else 0
        if in_tab and cur is not None and cur['table'] and all(body[j].in_table for j in range(cur['last'], k + 1)):
            cur['items'].append(d)
        else:
            cur = {'table': bool(in_tab), 'items': [d]}
            groups.append(cur)
        cur['last'] = k

    # 等價字元：外觀相同、排版時被統一換掉的字元（例：間隔號・→．），只計數、不列明細
    equiv = []
    for pair in cfg['排版比對'].get('等價字元', '').split('|'):
        if '=' in pair:
            a, b = pair.split('=', 1)
            equiv.append((a.strip(), b.strip()))

    def same(x, y):
        for a, b in equiv:
            x, y = x.replace(a, b), y.replace(a, b)
        return x == y

    # 排版稿只排了前段：最後一串「排版稿沒有」的差異都落在排版稿結尾 → 收成一筆
    tail_from = None
    k = len(groups)
    while k > 0 and not groups[k - 1]['table'] and all(p0 >= len(P) - 50 for _, _, p0, _ in groups[k - 1]['items']):
        k -= 1
    tail_chars = sum(d1 - d0 for g in groups[k:] for d0, d1, _, _ in g['items'])
    if tail_chars >= 1000:
        tail_from = k

    missing_notes_text = ''
    minor = Counter()
    for gi, g in enumerate(groups):
        if tail_from is not None and gi >= tail_from:
            if gi == tail_from:
                d0 = g['items'][0][0]
                emit('範圍外', '排版稿未含此後內容', dside, body, d0, min(d0 + 30, len(D)), pdf.main, len(P), len(P),
                     f'原稿從這裡起約 {tail_chars:,} 字（{len(groups) - tail_from:,} 處差異）在排版稿結尾之後都找不到；'
                     '排版稿可能只排到這裡。若排版稿應為全書，這就是漏排')
            continue
        if g['table']:
            d0 = min(x[0] for x in g['items']); d1 = max(x[1] for x in g['items'])
            p0 = min(x[2] for x in g['items']); p1 = max(x[3] for x in g['items'])
            a, b = Counter(D[d0:d1]), Counter(P[p0:p1])
            if a == b:
                minor['表格閱讀順序不同'] += 1
                emit('排版性', '表格閱讀順序不同', dside, body, d0, d1, pdf.main, p0, p1,
                     '表格內的字完全相同，只是抽取順序不同（原稿逐格、排版稿逐行）')
            else:
                lost = ''.join(sorted((a - b).elements()))[:40]
                extra = ''.join(sorted((b - a).elements()))[:40]
                emit('實質', '表格內容不同', dside, body, d0, d1, pdf.main, p0, p1,
                     f'表格順序無法逐字對照，改比字數：排版稿少了「{lost}」、多了「{extra}」')
            continue
        d0, d1, p0, p1 = g['items'][0]
        dtxt, ptxt = D[d0:d1], P[p0:p1]
        para = owner(d0)
        level, kind, extra = '實質', None, ''
        if dtxt and ptxt and same(dtxt, ptxt):
            minor[f'等價字元 {dtxt}→{ptxt}'] += 1
            continue
        if not dtxt and re.fullmatch(r'[.．…·‧・]+', ptxt):
            minor['目次引線'] += 1
            continue
        if not dtxt and para and para.listed and d0 == dstarts[dside.owner[min(d0, len(D) - 1)]] and len(ptxt) <= 8:
            level, kind, extra = '排版性', '自動編號或項目符號', '原稿這段用 Word 自動編號／項目符號，符號不在文字裡'
        elif dtxt and all(0xE000 <= ord(c) <= 0xF8FF for c in dtxt) and len(ptxt) <= 2:
            level, kind, extra = '排版性', '符號字型', '原稿是符號字型的私用區字元（例：Wingdings），排版稿顯示為對應符號；確認符號正確'
        elif ptxt == '-' and not dtxt and (p1 - 1) in pdf.main.line_ends:
            level, kind, extra = '排版性', '行末斷字', '排版稿在行末把英文字斷開加了連字號'
        elif len(dtxt) >= 8 and not ptxt and dtxt in P:
            kind, extra = '位置移動', '這段文字在排版稿別處完整出現，多半是圖說或框文被移位；確認位置是否恰當'
        elif len(ptxt) >= 8 and not dtxt and ptxt in D:
            kind, extra = '位置移動', '這段文字在原稿別處出現'
        elif dtxt and not ptxt and (d0, d1) == (dstarts[dside.owner[d0]], dstarts[dside.owner[d0]] + dlens[dside.owner[d0]]):
            kind, extra = '整段漏排', '原稿這一整段在排版稿找不到'
        elif len(ptxt) >= 4 and not dtxt and ptxt in nside.text:
            kind, extra = '註腳混入正文', '這段是原稿的註腳文字，抽取時被當成正文；通常是註腳字級與正文相同'
            missing_notes_text += ptxt
        if level == '排版性':
            minor[kind] += 1
        emit(level, kind or _classify(dtxt, ptxt), dside, body, d0, d1, pdf.main, p0, p1, extra)

    # --- 註腳 ---
    if notes:
        ndiffs = collate(nside, nstarts, [len(normalize(p.text)[0]) for p in notes], pdf.notes)
        skipped = 0
        for d0, d1, p0, p1 in ndiffs:
            dtxt, ptxt = nside.text[d0:d1], pdf.notes.text[p0:p1]
            if not dtxt and re.fullmatch(r'[0-9*†‡]+', ptxt):
                skipped += 1      # 註腳開頭的編號，原稿是自動編號
                continue
            if dtxt and not ptxt and dtxt in missing_notes_text:
                continue          # 已在正文裡報過「註腳混入正文」
            emit('實質', _classify(dtxt, ptxt), nside, notes, d0, d1, pdf.notes, p0, p1, '註腳')
        res.notes.append(f'原稿註腳／尾註 {len(notes)} 則；排版稿註腳區抽到 {len(pdf.notes.text):,} 字；略過註腳編號 {skipped} 處')

    # --- 摘要 ---
    res.rows.sort(key=lambda r: {'實質': 0, '範圍外': 1}.get(r[0], 2))   # 實質差異排前面，同級維持書中順序
    shown = Counter(r[1] for r in res.rows if r[0] == '排版性')
    n_major = sum(1 for r in res.rows if r[0] == '實質')
    n_minor = sum(1 for r in res.rows if r[0] == '排版性')
    res.notes.insert(0, f'實質差異 {n_major} 筆、排版性差異 {n_minor} 筆'
                        + (f'（{"、".join(f"{k} {v}" for k, v in shown.items())}）' if shown else ''))
    hidden = {k: v for k, v in minor.items() if k not in shown}
    if hidden:
        res.notes.insert(1, '未列入明細（只計數）：' + '、'.join(f'{k} {v} 處' for k, v in hidden.items()))
    res.notes.insert(0, f'排版稿 {pdf.n_pages} 頁、正文 {len(pdf.main.text):,} 字（正文字級 {pdf.body_size}）；'
                        f'原稿正文 {len(dside.text):,} 字；移除上標注碼 {pdf.marks_dropped} 個、頁首頁尾 {len(pdf.hf_lines)} 行')
    q_pdf, q_doc = punct_join_rate(pdf.main.text), punct_join_rate(dside.text)
    note = f'全形標點錯接：排版稿每萬字 {q_pdf:.1f} 處、原稿 {q_doc:.1f} 處'
    if q_pdf > 1 and q_pdf > q_doc + 1:
        note += '——⚠️ 排版稿明顯偏高，可能是抽取行序錯亂，差異清單請先抽幾頁對照 PDF 再判讀'
    res.notes.append(note)

    hf = {}
    for pno, t in pdf.hf_lines:
        key = re.sub(r'\d+', '#', t)
        hf.setdefault(key, [0, pno, t])[0] += 1
    res.table = [['被當成頁首頁尾排除的文字（數字以 # 代表）', '出現頁數', '首見 PDF 頁', '例']] + \
        sorted(([k, n, p, t] for k, (n, p, t) in hf.items()), key=lambda r: -r[1])
    res.table_title = '已排除的頁首頁尾'
    res.notes.append('請看「已排除的頁首頁尾」確認沒有正文被誤排除；只出現一兩次的長句要特別留意')
    return res


def punct_join_rate(text):
    n = len(re.findall(r'[，。、；：？！]{2}', text))
    cjk = len(re.findall(f'[{CJK}]', text))
    return n / cjk * 10000 if cjk else 0.0
