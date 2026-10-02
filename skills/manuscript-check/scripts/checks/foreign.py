"""⑧ 外文拼寫頻率比對：全書罕見的外文詞，若只差一個字母就等於全書高頻詞，列為疑似拼錯。

判準：罕見形（1–3 次）對高頻形（≥8 次且 ≥5 倍）、編輯距離 1。
大小寫視為不同詞，但只差大小寫的配對不算（Fujikuro 人名、fujikuroi 種小名是不同用法）。
候選要看上下文判斷，不能直接當錯誤清單。
"""
import re
from collections import Counter

from .common import Hit, Result


def edit1(a, b):
    """a、b 是否剛好差一次增、刪、改。"""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    if len(a) > len(b):
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    return a[i:] == b[i + 1:]


def run(doc, cfg):
    res = Result('⑧ 外文拼寫')
    sec = cfg['外文']
    min_len = sec.getint('最短字母數', 5)
    rare_max = sec.getint('罕見上限', 3)
    freq_min = sec.getint('高頻下限', 8)
    ratio = sec.getint('倍數', 5)
    word_re = re.compile(r'[A-Za-zÀ-ÖØ-öø-ÿ]{%d,}' % min_len)

    freq = Counter()
    first = {}
    for p in doc.paras:
        for m in word_re.finditer(p.text):
            w = m.group()
            freq[w] += 1
            first.setdefault(w, (p, m.start(), m.end()))
    if not freq:
        res.notes.append('稿件沒有外文詞，本項未執行')
        return res

    frequent = [w for w, n in freq.items() if n >= freq_min]
    for w, n in sorted(freq.items()):
        if n > rare_max:
            continue
        for f in frequent:
            if freq[f] >= n * ratio and w.lower() != f.lower() and edit1(w, f):
                p, a, b = first[w]
                res.hits.append(Hit('疑似拼錯', p, w, a, b, f'出現 {n} 次；全書高頻形「{f}」出現 {freq[f]} 次'))
                break

    once = sorted(w for w, n in freq.items() if n == 1)
    res.table = [['只出現一次的外文詞', '章', '位置', '前後文']] + \
        [[w, first[w][0].chapter, first[w][0].loc, Hit('', first[w][0], w, first[w][1], first[w][2]).context()]
         for w in once]
    res.table_title = '外文單次詞'
    res.notes.append(f'外文詞（{min_len} 字母以上）共 {len(freq):,} 種；只出現一次的 {len(once):,} 種另列「外文單次詞」補看——頻率門檻抓不到重複出現的錯字')
    return res
