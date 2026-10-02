"""① 標點：成對符號配對、中文夾半形標點、連續標點、刪節號與破折號、疊字。"""
import re
from collections import Counter

from .common import CJK, Hit, Result, covered, read_lines

PAIRS = {'「': '」', '『': '』', '（': '）', '《': '》', '〈': '〉', '【': '】', '〔': '〕',
         '“': '”', '‘': '’', '(': ')', '[': ']'}
CLOSERS = {v: k for k, v in PAIRS.items()}

HALF_BETWEEN = re.compile(f'(?<=[{CJK}])[,;:!?.](?=[{CJK}])')
HALF_PAREN = re.compile(f'(?<=[{CJK}])[()]|[()](?=[{CJK}])')
DOUBLE_PUNCT = re.compile(r'[，、；：。][，、；：。！？]|[！？][，、；：。]')
SINGLE_ELLIPSIS = re.compile(r'(?<!…)…(?!…)')
FAKE_ELLIPSIS = re.compile(r'\.{3,}|。{3,}|．{3,}')
SINGLE_DASH = re.compile(r'(?<![—─])[—─](?![—─])')
DUP1 = re.compile(f'([{CJK}])\\1')
DUP2 = re.compile(f'([{CJK}]{{2}})\\1')


def _pairs(p, hits, next_text):
    stack = []
    t = p.text
    for i, ch in enumerate(t):
        if ch in PAIRS:
            stack.append((ch, i))
        elif ch in CLOSERS:
            # 英文縮寫的撇號（don’t）不是引號
            if ch == '’' and 0 < i < len(t) - 1 and t[i - 1].isalpha() and t[i + 1].isalpha():
                continue
            if stack and stack[-1][0] == CLOSERS[ch]:
                stack.pop()
            else:
                hits.append(Hit('多出的閉合符號', p, ch, i, i + 1, f'前面沒有對應的「{CLOSERS[ch]}」'))
    for ch, i in stack:
        note = f'段落結束前沒有「{PAIRS[ch]}」'
        if ch == '「' and next_text.lstrip().startswith('「'):
            note += '；下一段以「開頭，可能是跨段引文（依慣例只在最後一段閉合）'
        hits.append(Hit('未閉合', p, ch, i, i + 1, note))


def run(doc, cfg):
    res = Result('① 標點')
    listed = read_lines(cfg['標點'].get('疊字白名單', ''))
    white = {w for w in listed if len(w) == 2 or len(w) == 4 and w[:2] == w[2:]}
    context = [w for w in listed if w not in white]   # 較長的詞：命中落在這個詞裡就不報
    paras = doc.paras
    dash_forms = {'——': 0, '──': 0, '－－': 0}
    for k, p in enumerate(paras):
        t = p.text
        nxt = paras[k + 1].text if k + 1 < len(paras) and paras[k + 1].part == p.part else ''
        _pairs(p, res.hits, nxt)
        for m in HALF_BETWEEN.finditer(t):
            res.hits.append(Hit('半形標點夾在中文間', p, m.group(), m.start(), m.end()))
        for m in HALF_PAREN.finditer(t):
            res.hits.append(Hit('半形括號緊鄰中文', p, m.group(), m.start(), m.end(), '依體例判斷是否改全形'))
        for m in DOUBLE_PUNCT.finditer(t):
            res.hits.append(Hit('連續標點', p, m.group(), m.start(), m.end()))
        for m in SINGLE_ELLIPSIS.finditer(t):
            res.hits.append(Hit('刪節號', p, m.group(), m.start(), m.end(), '只有一個「…」，通常應為「……」'))
        for m in FAKE_ELLIPSIS.finditer(t):
            res.hits.append(Hit('刪節號', p, m.group(), m.start(), m.end(), '以句點代替刪節號'))
        for m in SINGLE_DASH.finditer(t):
            res.hits.append(Hit('破折號', p, m.group(), m.start(), m.end(), '只有一格，通常應佔兩格'))
        for form in dash_forms:
            dash_forms[form] += t.count(form)
        for m in DUP1.finditer(t):
            s = m.start()
            # AABB 型疊詞（的的確確、清清楚楚）不報
            nxt2, prv2 = t[s + 2:s + 4], t[max(0, s - 2):s]
            if (len(nxt2) == 2 and nxt2[0] == nxt2[1]) or (len(prv2) == 2 and prv2[0] == prv2[1]):
                continue
            if m.group() in white or covered(t, s, m.end(), context):
                continue
            res.hits.append(Hit('疊字', p, m.group(), s, m.end(), '確認是否誤植'))
        for m in DUP2.finditer(t):
            if m.group() not in white and not covered(t, m.start(), m.end(), context):
                res.hits.append(Hit('詞語重複', p, m.group(), m.start(), m.end(), '確認是否誤植'))
    # 疊字多半是跨詞界的巧合（管理＋理性），先列種類統計讓編輯整類略過；少見的排前面，較可能是真誤植
    species = Counter(h.match for h in res.hits if h.category in ('疊字', '詞語重複'))
    dup = sorted((h for h in res.hits if h.category in ('疊字', '詞語重複')), key=lambda h: (species[h.match], h.match))
    res.hits = [h for h in res.hits if h.category not in ('疊字', '詞語重複')] + dup
    if species:
        example = {}
        for h in dup:
            example.setdefault(h.match, h.context(6))
        res.table = [['疊字／重複詞', '次數', '例']] + [[w, n, example[w]] for w, n in sorted(species.items(), key=lambda x: -x[1])]
        res.table_title = '疊字種類'
        res.notes.append('疊字多為跨詞界巧合（例：管理＋理性），可看「疊字種類」整類略過；確認無誤的可寫進 設定/疊字白名單.txt')

    used = {f: n for f, n in dash_forms.items() if n}
    if len(used) > 1:
        res.hits.append(Hit('破折號寫法混用', None, '、'.join(f'{f}×{n}' for f, n in used.items()),
                            note='全書破折號有多種寫法，依體例統一'))
    return res
