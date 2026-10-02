"""讀 docx 的文字層：內文（含表格、文字方塊）、註腳、尾註。

以「接受全部追蹤修訂後」的文字為準：刪除中的文字不讀，插入中的文字照讀。
只讀不寫，不會改動稿件。
"""
import re
import zipfile
from dataclasses import dataclass

from lxml import etree

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
MC = 'http://schemas.openxmlformats.org/markup-compatibility/2006'


def q(tag):
    return f'{{{W}}}{tag}'


# 這些元素底下的內容不算正文：修訂刪除、搬移來源、相容替代內容（mc:Fallback 會重複一份文字方塊）
SKIP = {q('del'), q('moveFrom'), f'{{{MC}}}Fallback'}


@dataclass
class Para:
    part: str             # 內文／註腳／尾註
    num: int              # 內文：第幾段（只算有字的段落）；註腳／尾註：編號
    text: str
    style: str            # 樣式名稱
    level: int = None     # 標題層級（1 起算），不是標題則為 None
    auto_num: bool = False  # 標題是否使用 Word 自動編號（編號不在文字裡）
    chapter: str = ''     # 所屬的一級標題
    listed: bool = False    # 段落有自動編號或項目符號（排版稿會多出編號或符號）
    in_table: bool = False  # 段落在表格裡

    @property
    def loc(self):
        if self.part == '內文':
            return f'第 {self.num} 段'
        return f'{self.part} {self.num}'


@dataclass
class Doc:
    path: str
    paras: list

    @property
    def body(self):
        return [p for p in self.paras if p.part == '內文']


def _walk_paras(node):
    """依文件順序產生所有 w:p（含表格與文字方塊內的），略過 SKIP 區。"""
    for child in node:
        if child.tag in SKIP:
            continue
        if child.tag == q('p'):
            yield child
        yield from _walk_paras(child)


def _para_text(p):
    out = []

    def walk(node):
        for ch in node:
            tag = ch.tag
            if tag in SKIP or tag == q('p') or tag == q('txbxContent'):
                continue  # 巢狀段落（文字方塊）另外算
            if tag == q('t'):
                out.append(ch.text or '')
            elif tag == q('tab'):
                out.append('\t')
            elif tag in (q('br'), q('cr')):
                out.append('\n')
            elif tag == q('noBreakHyphen'):
                out.append('‑')
            elif tag == q('sym'):
                code = ch.get(q('char'))
                if code:
                    out.append(chr(int(code, 16)))
            else:
                walk(ch)
    walk(p)
    return ''.join(out)


def _load_styles(z):
    styles = {}
    if 'word/styles.xml' not in z.namelist():
        return styles
    root = etree.fromstring(z.read('word/styles.xml'))
    for s in root.iter(q('style')):
        sid = s.get(q('styleId'))
        name_el = s.find(q('name'))
        based = s.find(q('basedOn'))
        ppr = s.find(q('pPr'))
        lvl = ppr.find(q('outlineLvl')) if ppr is not None else None
        num = ppr.find(q('numPr')) if ppr is not None else None
        styles[sid] = {
            'name': name_el.get(q('val')) if name_el is not None else sid,
            'based': based.get(q('val')) if based is not None else None,
            'lvl': int(lvl.get(q('val'))) if lvl is not None else None,
            'num': num is not None,
        }
    return styles


def _style_attr(styles, sid, key):
    seen = set()
    while sid and sid in styles and sid not in seen:
        seen.add(sid)
        v = styles[sid][key]
        if v not in (None, False):
            return v
        sid = styles[sid]['based']
    return None


HEADING_NAME = re.compile(r'^(?:heading|標題)\s*(\d)$', re.I)


def _heading_level(p, styles):
    ppr = p.find(q('pPr'))
    sid = None
    if ppr is not None:
        lvl = ppr.find(q('outlineLvl'))
        if lvl is not None:
            v = int(lvl.get(q('val')))
            return v + 1 if v < 9 else None
        ps = ppr.find(q('pStyle'))
        sid = ps.get(q('val')) if ps is not None else None
    if sid:
        v = _style_attr(styles, sid, 'lvl')
        if v is not None:
            return v + 1 if v < 9 else None
        m = HEADING_NAME.match(styles.get(sid, {}).get('name', ''))
        if m:
            return int(m.group(1))
    return None


def _style_name(p, styles):
    ppr = p.find(q('pPr'))
    ps = ppr.find(q('pStyle')) if ppr is not None else None
    sid = ps.get(q('val')) if ps is not None else None
    return styles.get(sid, {}).get('name', sid or 'Normal')


def _auto_num(p, styles):
    ppr = p.find(q('pPr'))
    if ppr is not None and ppr.find(q('numPr')) is not None:
        return True
    ps = ppr.find(q('pStyle')) if ppr is not None else None
    return bool(ps is not None and _style_attr(styles, ps.get(q('val')), 'num'))


def _notes(z, part_name, tag, ref_order, label):
    if f'word/{part_name}' not in z.namelist():
        return []
    root = etree.fromstring(z.read(f'word/{part_name}'))
    notes = {}
    for n in root.iter(q(tag)):
        if n.get(q('type')) in ('separator', 'continuationSeparator', 'continuationNotice'):
            continue
        text = '\n'.join(t for t in (_para_text(p) for p in _walk_paras(n)) if t)
        notes[n.get(q('id'))] = text
    out = []
    for i, nid in enumerate(ref_order, 1):
        if nid in notes:
            out.append(Para(label, i, notes[nid], label))
    return out


def load(path):
    if not path.lower().endswith(('.docx', '.docm')):
        raise ValueError('只支援 .docx／.docm，舊版 .doc 請先在 Word 另存新檔為 .docx')
    with zipfile.ZipFile(path) as z:
        styles = _load_styles(z)
        root = etree.fromstring(z.read('word/document.xml'))
        body = root.find(q('body'))
        paras = []
        n = 0
        chapter = ''
        fn_order, en_order = [], []
        note_chapter = {}
        for p in _walk_paras(body):
            text = _para_text(p)
            level = _heading_level(p, styles) if text.strip() else None
            if level == 1:
                chapter = text.strip()
            for el in p.iter(q('footnoteReference'), q('endnoteReference')):
                if not any(a.tag in SKIP for a in el.iterancestors()):
                    kind = '註腳' if el.tag == q('footnoteReference') else '尾註'
                    (fn_order if kind == '註腳' else en_order).append(el.get(q('id')))
                    note_chapter[(kind, el.get(q('id')))] = chapter
            if not text.strip():
                continue
            n += 1
            para = Para('內文', n, text, _style_name(p, styles), level,
                        _auto_num(p, styles) if level else False, chapter)
            para.listed = _auto_num(p, styles)
            para.in_table = any(a.tag == q('tc') for a in p.iterancestors())
            paras.append(para)
        notes = _notes(z, 'footnotes.xml', 'footnote', fn_order, '註腳') + \
            _notes(z, 'endnotes.xml', 'endnote', en_order, '尾註')
    # 註腳、尾註掛在引用它的那一章
    for nt in notes:
        order = fn_order if nt.part == '註腳' else en_order
        nt.chapter = note_chapter.get((nt.part, order[nt.num - 1]), '')
    return Doc(path, paras + notes)
