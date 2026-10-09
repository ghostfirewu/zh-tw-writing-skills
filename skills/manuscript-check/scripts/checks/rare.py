"""⑩ 罕用字清單：列出稿件中標準 Big5 沒收的字，交給美編確認排版字型有沒有這些字。

不需要知道美編用什麼字型：Big5 以外的字（例：堃、啓、擴充 B 區的𠀋）是一般中文字型最容易缺的，
先列出來讓美編逐字確認，避免印出來變成方塊或被替換成別的字型。
西文字母（含重音字母）與一般標點由西文字型負責，不列。
"""
import unicodedata
from collections import OrderedDict
from functools import lru_cache

from .common import Hit, Result
from .simplified import gb_only_chars, taiwan_chars


@lru_cache(None)
def big5_chars():
    out = set()
    for b1 in range(0xA1, 0xFA):
        for b2 in list(range(0x40, 0x7F)) + list(range(0xA1, 0xFF)):
            code = (b1 << 8) | b2
            if not (0xA140 <= code <= 0xA3BF or 0xA440 <= code <= 0xC67E or 0xC940 <= code <= 0xF9D5):
                continue   # 標準 Big5：符號區＋常用字＋次常用字（不含各家廠商擴充）
            # Python 的 big5 與 Windows 的 cp950 在符號區對應不同（例：～），兩份都算
            for enc in ('big5', 'cp950'):
                try:
                    out.add(bytes([b1, b2]).decode(enc))
                except UnicodeDecodeError:
                    pass
    return frozenset(out)


def _block(ch):
    o = ord(ch)
    for a, b, name in ((0x4E00, 0x9FFF, '基本區'), (0x3400, 0x4DBF, '擴充 A 區'), (0x20000, 0x2A6DF, '擴充 B 區'),
                       (0x2A700, 0x2EE5F, '擴充 C～F、I 區'), (0x30000, 0x323AF, '擴充 G～H 區'),
                       (0xF900, 0xFAFF, '相容區'), (0x2F800, 0x2FA1F, '相容補充區'),
                       (0x2E80, 0x2FDF, '部首'), (0x3100, 0x312F, '注音'), (0x31A0, 0x31BF, '注音擴充')):
        if a <= o <= b:
            return name
    return None


def _skip(ch):
    o = ord(ch)
    if o < 0x250 or 0x1E00 <= o <= 0x1EFF or 0x2000 <= o <= 0x206F:
        return True   # 西文字母、重音字母、一般標點：西文字型負責
    if 0xE000 <= o <= 0xF8FF or o >= 0xF0000:
        return True   # 私用區已列在「② 異常字元」
    return unicodedata.category(ch)[0] in 'CZ'   # 控制字元、空白


def run(doc, cfg):
    res = Result('⑩ 罕用字')
    big5 = big5_chars()
    gb_only = gb_only_chars() - taiwan_chars(cfg)
    found = OrderedDict()   # 字 -> [次數, 首見段落, 位置]
    for p in doc.paras:
        for i, ch in enumerate(p.text):
            if ch in big5 or _skip(ch):
                continue
            if ch not in found:
                found[ch] = [0, p, i]
            found[ch][0] += 1

    for ch, (n, p, i) in found.items():
        block = _block(ch)
        cat = f'漢字（{block}）' if block else '符號'
        note = f'全書 {n} 處'
        if not block:
            note += f'；{unicodedata.name(ch, "")}'
        if ch in gb_only:
            note += '；也是簡體字，已列在「② 簡體字」，改成正體後就不必確認字型'
        res.hits.append(Hit(cat, p, ch, i, i + 1, note))
    # 漢字在前、符號在後；簡體字排到最後（改成正體就不必確認）；同類依首見順序
    order = {ch: k for k, ch in enumerate(found)}
    res.hits.sort(key=lambda h: (not h.category.startswith('漢字'), h.match in gb_only, order[h.match]))

    res.table = [['字', '碼位', '區段', '次數', '首見章', '首見位置']] + [
        [h.match, f'U+{ord(h.match):04X}', h.category, found[h.match][0], h.para.chapter, h.para.loc] for h in res.hits]
    res.table_title = '罕用字清單（交美編）'
    res.notes.append(f'標準 Big5 沒收的字共 {len(found)} 個（每字一列）；「罕用字清單（交美編）」可直接複製給美編確認字型')
    return res
