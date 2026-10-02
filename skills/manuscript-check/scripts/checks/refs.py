"""⑨ 參考文獻：內文的「作者—年份」引用與書目清單雙向比對。

支援的引用寫法：(Smith, 2010)、(Smith & Lee, 2010; Wang, 2012)、Smith (2010)、（王小明，2015）、王小明（2015）。
比對方式：年份（含 2010a 這類字尾）相同，且書目第一作者的姓出現在引用文字裡，就算對上。
編號制（[1]、上標注碼）的引用不在本項範圍。
"""
import re

from .common import CJK, Hit, Result

BIB_HEAD = re.compile(r'^\s*(參考文獻|參考書目|引用文獻|參考資料|文獻|書目|References|Bibliography|Works Cited|Reference List)\s*$', re.I)
YEAR = re.compile(r'(?<![0-9])(1[5-9]\d\d|20\d\d)([a-z])?(?![0-9])')
NARR_NAME = re.compile(r"([A-Z][A-Za-z'’-]+|[" + CJK + r"]{2,6})(?:\s+et al\.?|等人?)?\s*$")
PAREN = re.compile(r'[（(]([^（）()]{1,300})[)）]')
NON_NAME = {'', '西元', '民國', '約', 'c.', 'ca.', 'circa', '公元', '西元前', '約於'}


def _entry_key(text):
    t = text.strip()
    if not t:
        return None
    if re.match(f'[{CJK}]', t):
        m = re.match(f'[{CJK}]+', t)
        return m.group() if m else None
    m = re.match(r'[^,，.(（]+', t)
    return m.group().strip() if m else None


def _find_bib(doc):
    body = doc.body
    for i, p in enumerate(body):
        if BIB_HEAD.match(p.text.strip()):
            entries = []
            for q in body[i + 1:]:
                if q.level and (p.level is None or q.level <= p.level):
                    break
                if q.level:
                    continue
                entries.append(q)
            return p, entries
    return None, []


def _citations(paras):
    """產生 (年份, 可能含作者的文字, 第一作者, 段落, 起, 迄)。"""
    for p in paras:
        t = p.text
        for m in PAREN.finditer(t):
            inner = m.group(1)
            pieces = re.split(r'[;；]', inner)
            only_year = YEAR.fullmatch(inner.strip().split(',')[0].split('，')[0].strip())
            if only_year and len(pieces) == 1:
                # 敘述式：Smith (2010)、王小明（2015）——作者在括號前面
                before = t[max(0, m.start() - 40):m.start()]
                wm = NARR_NAME.search(before)
                if wm:
                    yield only_year.group(), before, wm.group(1), p, m.start(), m.end()
                continue
            for piece in pieces:
                ym = YEAR.search(piece)
                if not ym:
                    continue
                if piece[ym.end():ym.end() + 1] == '年' or piece[ym.end():ym.end() + 2].strip().startswith('年'):
                    continue   # 「1990 年代」「2010 年」不是引用
                name = piece[:ym.start()].strip().rstrip(',，').strip()
                if name in NON_NAME or not re.search(f'[A-Za-z{CJK}]', name):
                    continue
                who = re.split(r'\s*(?:&|\band\b|與|和|、|et al\.?|等人?)\s*', name)[0].strip()
                yield ym.group(), name, who, p, m.start(), m.end()


def run(doc, cfg):
    res = Result('⑨ 參考文獻')
    head, entries = _find_bib(doc)
    if head is None:
        res.notes.append('找不到參考文獻標題（參考文獻／參考書目／References 等獨立一行），本項未執行')
        return res

    bib = []
    seen_text = {}
    for e in entries:
        ym = YEAR.search(e.text)
        key = _entry_key(e.text)
        norm = re.sub(r'\s+', '', e.text)
        if norm in seen_text:
            res.hits.append(Hit('書目重複', e, key or e.text[:20], note=f'與 {seen_text[norm].loc} 完全相同'))
            continue
        seen_text[norm] = e
        if not ym or not key:
            res.hits.append(Hit('書目無法解析', e, e.text[:30], note='找不到作者或年份，未納入比對'))
            continue
        bib.append({'key': key, 'year': ym.group(), 'para': e, 'used': False})

    skip = {id(e) for e in entries} | {id(head)}
    body_paras = [p for p in doc.paras if id(p) not in skip]
    n_cite = 0
    for year, name, who, p, a, b in _citations(body_paras):
        n_cite += 1
        matched = [x for x in bib if x['year'] == year and x['key'] in name]
        for x in matched:
            x['used'] = True
        if not matched:
            res.hits.append(Hit('引用了但書目沒有', p, f'{who} {year}', a, b, '書目找不到同年份、同作者的條目'))
    for x in bib:
        if not x['used']:
            res.hits.append(Hit('書目有但內文沒引用', x['para'], f"{x['key']} {x['year']}"))
    res.notes.append(f'書目 {len(entries)} 條（可比對 {len(bib)} 條）；內文偵測到作者—年份引用 {n_cite} 處')
    if n_cite == 0:
        res.notes.append('內文沒有偵測到作者—年份引用；若本書用編號或註腳引用，本項結果不適用')
    return res
