"""③ 同書異形並存：同一本書裡，詞表的舊形與新形同時出現；以及譯名表的變體。

詞表格式：原字,改字,模式,例外（見 設定/詞表_詞換詞.txt 檔頭）。
"""
from .common import Hit, Result, parse_token, read_lines


def _first(doc, word):
    for p in doc.paras:
        i = p.text.find(word)
        if i >= 0:
            return p, i
    return None, -1


def _count(text, word, excepts=()):
    n = text.count(word)
    for e in excepts:
        n -= text.count(e) * e.count(word)
    return n


def run(doc, cfg):
    res = Result('③ 異形並存')
    sec = cfg['異形詞']
    text = '\n'.join(p.text for p in doc.paras)

    rules = []
    for path in filter(None, sec.get('詞表', '').split('|')):
        for ln in read_lines(path):
            f = ln.split(',')
            if len(f) < 2:
                continue
            src, tgt = parse_token(f[0]), parse_token(f[1])
            mode = f[2].strip() if len(f) > 2 else ''
            if mode == '標' or not src or not tgt or src == tgt:
                continue
            excepts = [e for e in f[3].split('|') if e] if len(f) > 3 else []
            rules.append((src, tgt, excepts))

    seen = set()
    for src, tgt, excepts in rules:
        if (src, tgt) in seen:
            continue
        seen.add((src, tgt))
        n_src = _count(text, src, excepts)
        if n_src <= 0:
            continue
        n_tgt = _count(text, tgt)
        if tgt in src:   # 新形包含在舊形裡（例：英寸英寸→英寸），扣掉重複計數
            n_tgt -= n_src * src.count(tgt)
        p, i = _first(doc, src)
        note = f'舊形「{src}」{n_src} 處、新形「{tgt}」{n_tgt} 處'
        if len(src) == 1 or len(tgt) == 1:
            note += '；單字規則，並存多半來自不同的詞，請抽查'
        cat = '並存' if n_tgt > 0 else '只見舊形'
        res.hits.append(Hit(cat, p, f'{src}／{tgt}', i, i + len(src), note))

    for ln in read_lines(sec.get('譯名表', '')):
        std, _, alts = ln.partition(',')
        found = [(a, text.count(a)) for a in alts.split('|') if a and text.count(a)]
        if found:
            p, i = _first(doc, found[0][0])
            note = f'標準譯名「{std}」{text.count(std)} 處；' + '、'.join(f'「{a}」{n} 處' for a, n in found)
            res.hits.append(Hit('譯名不一', p, std, i, i + len(found[0][0]), note))

    res.hits.sort(key=lambda h: {'並存': 0, '譯名不一': 1, '只見舊形': 2}[h.category])
    if not rules:
        res.notes.append('未設定詞表，只檢查譯名表')
    return res
