#!/usr/bin/env python3
"""改寫前後比對：找出改寫時「加料」或「漏掉」的候選。只用 Python 標準函式庫，不呼叫任何模型。

用法：
    python3 rewrite_diff.py 原文.md 改寫後.md
    python3 rewrite_diff.py 原文.md 改寫後.md --json
結束代碼：有任何一筆增減（需要回頭對原文確認）＝1，完全沒有＝0，用法錯誤＝2。

拿來對照 references/rewrite-safety.md 的「改寫不加料」與「語氣強度兩個方向都不動」。
抓的東西：
  1. 數字（含百分比、日期、中文數字＋單位）：改寫後多出來的、不見的。
  2. 英文詞與引號「」內的內容：多出來的、不見的（專名、引語最怕被改）。
  3. 語氣用語的數量變化：保證、義務、推測、範圍限定、責任、完成度、因果、評價。
     推測或範圍限定變少、保證或完成度變多，代表強度可能被改高。
這是篩選器：每一筆都要回頭對原文判斷，換句話說的正常改寫也會被列出來。
預期內的結果：照規則刪掉墊片詞（「值得注意的是」）會讓「評價」變少，刪轉場詞會讓「因果」變少，把二元對比改成直述會讓「但」這類詞變少——確認是刻意刪的就好。
"""
import argparse
import json
import re
import sys
from collections import Counter

NUM = re.compile(
    r'\d+(?:[.,]\d+)*\s*(?:%|％|成|倍|萬|億|元|年|月|日|天|個|人|次|小時|分鐘|秒)?'
    r'|[零〇一二兩三四五六七八九十百千]+(?:成|倍|萬|億|元|年|人|次|小時|分鐘|天|週|星期|位|名|家|章|節|項|場|頁'
    r'|個(?=月|人|小時|星期|禮拜|工作天))'
)
LATIN = re.compile(r'[A-Za-z][A-Za-z0-9_.+#/-]*[A-Za-z0-9]|[A-Za-z]')
QUOTE = re.compile(r'「([^「」\n]+)」|『([^『』\n]+)』|“([^“”\n]+)”')

# 語氣用語。direction：'up'＝變多代表強度變高；'down'＝變少代表強度變高或但書被刪；None＝只報增減
MARKERS = {
    '保證': (r'保證|一定會|絕對|必定|必然|肯定會|確保|百分之百|100%', 'up'),
    '完成度': (r'已完成|已經完成|已上線|完成了|全面上線|正式上線', 'up'),
    '責任': (r'負責|主導|一手', 'up'),
    '因果': (r'導致|造成|證明了|證實|使得|因此|所以', 'up'),
    '推測': (r'可能|也許|或許|似乎|大概|據稱|據說|初步|估計|恐怕|傾向於|看起來', 'down'),
    '範圍限定': (r'但是|(?<!不)但(?!願)|除非|例外|僅限|(?<!不)(?<!僅)僅(?!僅)|只限|只有|只能|有限|限定|限於|至少|至多|最多|不超過|以內|前提是|條件是', 'down'),
    '進行中': (r'進行中|規劃中|研擬|預計|將於|試行|測試中', 'down'),
    '義務': (r'必須|務必|應該|應當|一定要|不得|禁止', None),
    '評價': (r'重要|關鍵|核心|不可或缺|值得|最好|最佳', None),
}


def normalize(text):
    text = re.sub(r'```.*?```', ' ', text, flags=re.S)
    text = re.sub(r'`[^`\n]*`', ' ', text)
    return text.replace('**', '').replace('__', '')


def tokens(rx, text):
    out = Counter()
    for m in rx.finditer(text):
        g = next((x for x in m.groups() if x), None) if m.groups() else m.group()
        if g:
            out[re.sub(r'\s+', '', g)] += 1
    return out


def compare(before, after):
    b, a = normalize(before), normalize(after)
    res = {'數字': {}, '英文詞': {}, '引號內容': {}, '語氣用語': []}
    for name, rx in (('數字', NUM), ('英文詞', LATIN), ('引號內容', QUOTE)):
        tb, ta = tokens(rx, b), tokens(rx, a)
        res[name] = {'多出來': sorted((ta - tb).elements()), '不見了': sorted((tb - ta).elements())}
    for name, (pat, direction) in MARKERS.items():
        nb, na = len(re.findall(pat, b)), len(re.findall(pat, a))
        if nb == na:
            continue
        risky = (direction == 'up' and na > nb) or (direction == 'down' and na < nb)
        res['語氣用語'].append({'類別': name, '原文': nb, '改寫後': na, '強度可能改高': risky})
    return res


def needs_review(res):
    """有任何一筆增減就要回頭看（⚠️ 只是提示哪幾筆最可能是改高強度）。"""
    if any(res[k]['多出來'] or res[k]['不見了'] for k in ('數字', '英文詞', '引號內容')):
        return True
    return bool(res['語氣用語'])


def report(res):
    lines = []
    for k in ('數字', '英文詞', '引號內容'):
        for label in ('多出來', '不見了'):
            if res[k][label]:
                lines.append(f'[{k}・{label}] ' + '、'.join(res[k][label]))
    for m in res['語氣用語']:
        flag = '　⚠️ 強度可能改高' if m['強度可能改高'] else ''
        lines.append(f"[語氣・{m['類別']}] {m['原文']} → {m['改寫後']}{flag}")
    if not lines:
        lines.append('沒有發現數字、專名、引語或語氣用語的增減。')
    return '\n'.join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description='改寫前後比對：找加料與漏掉的候選')
    ap.add_argument('before')
    ap.add_argument('after')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        pass
    try:
        with open(args.before, encoding='utf-8-sig', errors='replace') as f:
            before = f.read()
        with open(args.after, encoding='utf-8-sig', errors='replace') as f:
            after = f.read()
    except OSError as e:
        print(f'讀不到檔案：{e}', file=sys.stderr)
        return 2
    res = compare(before, after)
    print(json.dumps(res, ensure_ascii=False, indent=1) if args.json else report(res))
    return 1 if needs_review(res) else 0


if __name__ == '__main__':
    sys.exit(main())
