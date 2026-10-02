"""⑤ 統計：分章字數、無標點長串、長句、長段。"""
import re
from collections import OrderedDict

from .common import CJK, Hit, Result

PUNCT = '，。、；：！？…—─「」『』（）《》〈〉【】〔〕“”‘’,.;:!?()[]\n\t'
NO_PUNCT_RUN = re.compile(f'[^{re.escape(PUNCT)}]+')
SENT_END = re.compile(r'[^。！？；!?;]+[。！？；!?;]*')
CJK_RE = re.compile(f'[{CJK}]')
WORD_RE = re.compile(r'[A-Za-zÀ-ÖØ-öø-ÿ]+')


def run(doc, cfg):
    res = Result('⑤ 統計')
    sec = cfg['統計']
    max_run = sec.getint('無標點長串', 60)
    max_sent = sec.getint('長句', 150)
    max_para = sec.getint('長段', 600)

    chapters = OrderedDict()
    for p in doc.paras:
        name = p.chapter or '（第一個一級標題之前）'
        c = chapters.setdefault(name, {'中文字': 0, '英文詞': 0, '段落': 0, '註腳': 0})
        c['中文字'] += len(CJK_RE.findall(p.text))
        c['英文詞'] += len(WORD_RE.findall(p.text))
        c['段落' if p.part == '內文' else '註腳'] += 1
        if p.level:
            continue
        for m in NO_PUNCT_RUN.finditer(p.text):
            n = len(m.group().replace(' ', ''))
            if n > max_run:
                res.hits.append(Hit('無標點長串', p, f'{n} 字', m.start(), m.end(), f'連續 {n} 字沒有標點（門檻 {max_run}）'))
        for m in SENT_END.finditer(p.text):
            n = len(m.group().strip())
            if n > max_sent:
                res.hits.append(Hit('長句', p, f'{n} 字', m.start(), m.end(), f'門檻 {max_sent}'))
        n = len(p.text.strip())
        if p.part == '內文' and n > max_para:
            res.hits.append(Hit('長段', p, f'{n} 字', note=f'門檻 {max_para}'))

    res.table = [['章', '中文字數', '英文詞數', '段落數', '註腳／尾註數']] + \
        [[name, c['中文字'], c['英文詞'], c['段落'], c['註腳']] for name, c in chapters.items()]
    total = [sum(c[k] for c in chapters.values()) for k in ('中文字', '英文詞', '段落', '註腳')]
    res.table_title = '分章字數'
    res.notes.append(f'全書中文 {total[0]:,} 字、英文 {total[1]:,} 詞、{total[2]:,} 段、註腳／尾註 {total[3]:,} 則')
    return res
