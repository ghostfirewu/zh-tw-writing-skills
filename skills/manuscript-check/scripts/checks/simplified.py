"""② 簡體殘留、一簡多繁、錯轉繁、異常字元。

簡體字判準用字元集特徵（不用手寫字表）：GB2312 收錄、標準 Big5 沒收錄的漢字列為候選。
地名、日本人名、罕用植物名常屬誤報，由編輯逐字判斷。
"""
from collections import Counter, defaultdict
from functools import lru_cache

from .common import Hit, Result, covered, is_cjk, read_lines

PER_CHAR_CAP = 20   # 同一個字最多列幾處，其餘在說明欄計數

# 相容表意文字區裡其實是統一漢字的 12 個字，不算異常
COMPAT_UNIFIED = {0xFA0E, 0xFA0F, 0xFA11, 0xFA13, 0xFA14, 0xFA1F, 0xFA21, 0xFA23, 0xFA24, 0xFA27, 0xFA28, 0xFA29}


@lru_cache(None)
def gb_only_chars():
    gb = set()
    for b1 in range(0xB0, 0xF8):            # GB2312 一、二級漢字區
        for b2 in range(0xA1, 0xFF):
            try:
                gb.add(bytes([b1, b2]).decode('gb2312'))
            except UnicodeDecodeError:
                pass
    big5 = set()
    for b1 in range(0xA4, 0xFA):
        for b2 in list(range(0x40, 0x7F)) + list(range(0xA1, 0xFF)):
            code = (b1 << 8) | b2
            if not (0xA440 <= code <= 0xC67E or 0xC940 <= code <= 0xF9D5):   # 標準 Big5 常用＋次常用字
                continue
            try:
                big5.add(bytes([b1, b2]).decode('big5'))
            except UnicodeDecodeError:
                pass
    return frozenset(c for c in gb - big5 if is_cjk(c))


def _odd_char(ch):
    o = ord(ch)
    if 0xE000 <= o <= 0xF8FF or o >= 0xF0000:
        return '私用區字元（常見於 Wingdings 等符號字型或造字），排版時可能變成方塊'
    if 0xF900 <= o <= 0xFAFF and o not in COMPAT_UNIFIED:
        return '相容表意文字，外觀與標準字相同但碼位不同，可在 Word 用尋找取代換成標準字'
    if o in (0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF):
        return '零寬字元（看不見）'
    if o == 0xFFFD:
        return '亂碼替代字元（轉檔時遺失的字）'
    if o < 0x20 and ch not in '\t\n':
        return '控制字元'
    return None


def run(doc, cfg):
    res = Result('② 簡體與異常字元')
    sec = cfg['簡體']
    gb_only = gb_only_chars()

    seen = Counter()
    for p in doc.paras:
        for i, ch in enumerate(p.text):
            if ch in gb_only:
                seen[ch] += 1
                if seen[ch] <= PER_CHAR_CAP:
                    res.hits.append(Hit('簡體字', p, ch, i, i + 1))
            else:
                why = _odd_char(ch)
                if why:
                    res.hits.append(Hit('異常字元', p, f'U+{ord(ch):04X}', i, i + 1, why))
    for h in res.hits:
        if h.category == '簡體字' and seen[h.match] > PER_CHAR_CAP:
            h.note = f'全書共 {seen[h.match]} 處，只列前 {PER_CHAR_CAP} 處'

    # 一簡多繁：簡體形本身也是正體字，只能看二字組判斷
    suspects, excludes = {}, {}
    for ln in read_lines(sec.get('一簡多繁清單', '')):
        f = ln.split(',')
        suspects[f[0]] = set(w for w in f[1].split('|') if w) if len(f) > 1 else set()
        excludes[f[0]] = [w for w in f[2].split('|') if w] if len(f) > 2 else []
    species = defaultdict(lambda: [0, None])
    for p in doc.paras:
        t = p.text
        for i, ch in enumerate(t):
            if ch not in suspects or covered(t, i, i + 1, excludes[ch]):
                continue   # 這個字屬於排除詞（例：「若干部分」的干屬於「若干」）
            for a, b in ((i - 1, i + 1), (i, i + 2)):
                if a < 0 or b > len(t) or not all(is_cjk(c) for c in t[a:b]):
                    continue
                bg = t[a:b]
                species[bg][0] += 1
                if species[bg][1] is None:
                    species[bg][1] = p
                if bg in suspects[ch]:
                    res.hits.append(Hit('一簡多繁字組', p, bg, a, b, '疑似簡體殘留'))
    rows = []
    for bg, (n, p) in species.items():
        ch = bg[0] if bg[0] in suspects else bg[1]
        rows.append([bg, n, '是' if bg in suspects[ch] else '', ch, p.chapter, p.loc])
    rows.sort(key=lambda r: (r[2] != '是', r[3], -r[1]))
    res.table = [['二字組', '次數', '已知可疑', '字', '首見章', '首見位置']] + rows
    res.table_title = '一簡多繁字組全表'

    for w in read_lines(sec.get('錯轉清單', '')):
        for p in doc.paras:
            start = p.text.find(w)
            while start >= 0:
                res.hits.append(Hit('錯轉繁', p, w, start, start + len(w), '轉換器選錯繁體；跨詞界時為誤報（例：頭＋發燙）'))
                start = p.text.find(w, start + 1)

    res.notes.append('一簡多繁字集為手列、非全集（設定/一簡多繁.txt）；「一簡多繁字組全表」列出所有二字組供逐種判讀')
    return res
