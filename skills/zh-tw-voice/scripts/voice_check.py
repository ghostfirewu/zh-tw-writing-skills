#!/usr/bin/env python3
"""成品對照：拿寫好的草稿對照風格檔（voice.json），抓出「學過頭」或「不合場合」的地方。只用 Python 標準函式庫。

用法：
    python3 voice_check.py --register 社群 草稿.md
    python3 voice_check.py --register 正式 報告.md
    pbpaste | python3 voice_check.py --register 社群 -
選項：
    --register    社群｜正式（必填；由 agent 判斷，判斷不了就問使用者）
    --profile     直接指定 voice.json
    --config-dir  指定專案設定資料夾（預設自動找 .zh-tw-writing/，見下）
    --json        輸出 JSON
結束代碼：有「超出」或「長句」＝1，沒有＝0，用法錯誤或社群模式找不到風格檔＝2。

兩種場合：
  社群  某項特徵比使用者的習慣多太多（超過習慣頻率的 1.5 倍，且至少 2 次）→ 超出。
        例：作者平均一篇用一次「說真的」，草稿出現五次就會被抓。
        習慣上常用、草稿卻完全沒有的，列在「偏少」，只供參考，不影響結束代碼。
  正式  口語特徵（語氣詞、驚嘆號、波浪號、emoji）出現就列為超出，不看習慣；沒有風格檔也能跑。
兩種場合都會列出超過長句上限的句子（風格檔的「長句上限」，沒有風格檔時 100 字）。

這是篩選器：只看得到數得出來的特徵。像不像本人，最後還是要讀過才知道。

找風格檔的順序：--profile → --config-dir/voice.json → 環境變數 ZHTW_WRITING_DIR
→ $CLAUDE_PROJECT_DIR/.zh-tw-writing → 目前目錄/.zh-tw-writing
"""
import argparse
import importlib.util
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location('voice_profile', os.path.join(HERE, 'voice_profile.py'))
vp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vp)

CONFIG_NAME = '.zh-tw-writing'
REGISTERS = ('社群', '正式')
COLLOQUIAL = ('語氣詞', '驚嘆號', '波浪號', 'emoji')   # 正式場合一出現就報
TOLERANCE = 1.5
NOTES = {
    '語氣詞': '口語語氣詞（啦、吧、欸、喔……）',
    '驚嘆號': '驚嘆號',
    '波浪號': '波浪號',
    'emoji': 'emoji',
    '刪節號': '刪節號',
    '破折號': '破折號',
    '問號': '問號',
    '英文詞': '中英夾雜',
}


def find_config_dir(explicit=None, cwd=None):
    """找專案設定資料夾；找不到回 None。只看目前目錄，不往上層找。"""
    cands = [explicit, os.environ.get('ZHTW_WRITING_DIR')]
    if os.environ.get('CLAUDE_PROJECT_DIR'):
        cands.append(os.path.join(os.environ['CLAUDE_PROJECT_DIR'], CONFIG_NAME))
    cands.append(os.path.join(cwd or os.getcwd(), CONFIG_NAME))
    for c in cands:
        if c and os.path.isdir(c):
            return c
    return None


def long_sentences(text, limit):
    out = []
    for no, line in enumerate(text.split('\n'), 1):
        for s in vp.sentences(line):
            n = vp.sent_len(s)
            if n > limit:
                out.append({'行': no, '字數': n, '開頭': s[:15]})
    return out


def _allowed(rate, chars):
    return max(1, math.ceil(rate * chars / 1000 * TOLERANCE))


def check(text, profile, register):
    """profile：voice.json 的內容（正式模式可為 None）。"""
    chars = vp.char_count(vp.clean(text))
    c = vp.counts(text)
    over, under = [], []
    rates = (profile or {}).get('每千字', {})
    if register == '正式':
        for k in COLLOQUIAL:
            if c[k]:
                over.append({'項目': k, '草稿': c[k], '上限': 0, '說明': f'{NOTES[k]}不適合正式文體'})
    else:
        for k, n in c.items():
            rate = rates.get(k, 0)
            lim = _allowed(rate, chars)
            if n >= 2 and n > lim:
                over.append({'項目': k, '草稿': n, '上限': lim,
                             '說明': f'{NOTES.get(k, k)}比平常多：習慣每千字 {rate}，這篇約 {per(n, chars)}'})
            elif n == 0 and rate * chars / 1000 >= 2:
                under.append({'項目': k, '草稿': 0, '預期': round(rate * chars / 1000, 1),
                              '說明': f'平常常用{NOTES.get(k, k)}，這篇完全沒有'})
    t = vp.clean(text)
    for p, rate in (profile or {}).get('口頭禪', {}).items():
        n = t.count(p)
        lim = _allowed(rate, chars)
        if n >= 2 and n > lim:
            over.append({'項目': f'口頭禪：{p}', '草稿': n, '上限': lim,
                         '說明': f'習慣每千字 {rate}，這篇約 {per(n, chars)}；重複太多會變成新的模板'})
    limit = (profile or {}).get('長句上限', vp.DEFAULT_LONG)
    return {'場合': register, '字數': chars, '超出': over, '偏少': under,
            '長句': long_sentences(t, limit), '長句上限': limit}


def per(n, chars):
    return vp.per_k(n, chars)


def needs_review(res):
    return bool(res['超出'] or res['長句'])


def main(argv=None):
    ap = argparse.ArgumentParser(description='草稿對照風格檔（繁體中文）')
    ap.add_argument('file', help='草稿；- 為標準輸入')
    ap.add_argument('--register', required=True, choices=REGISTERS)
    ap.add_argument('--profile', help='voice.json 的路徑')
    ap.add_argument('--config-dir', help='專案設定資料夾（預設自動找 .zh-tw-writing/）')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        pass
    if args.config_dir and not os.path.isdir(args.config_dir):
        print(f'找不到設定資料夾：{args.config_dir}', file=sys.stderr)
        return 2
    path = args.profile
    if not path:
        d = find_config_dir(args.config_dir)
        if d and os.path.isfile(os.path.join(d, 'voice.json')):
            path = os.path.join(d, 'voice.json')
    profile = None
    if path:
        try:
            with open(path, encoding='utf-8-sig') as f:
                profile = json.load(f)
        except (OSError, ValueError) as e:
            print(f'讀不到風格檔 {path}：{e}', file=sys.stderr)
            return 2
    elif args.register == '社群':
        print('找不到風格檔 voice.json；先用 voice_profile.py --out .zh-tw-writing/voice.json 建檔', file=sys.stderr)
        return 2
    try:
        if args.file == '-':
            text = sys.stdin.buffer.read().decode('utf-8', errors='replace')
        else:
            with open(args.file, encoding='utf-8-sig', errors='replace') as f:
                text = f.read()
    except OSError as e:
        print(f'讀不到 {args.file}：{e}', file=sys.stderr)
        return 2
    res = check(text, profile, args.register)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        print(f"場合：{res['場合']}（風格檔：{path or '無'}）字數 {res['字數']}")
        for x in res['超出']:
            print(f"[超出] {x['項目']}：草稿 {x['草稿']} 次，上限 {x['上限']} 次。{x['說明']}")
        for x in res['長句']:
            print(f"[長句] 第 {x['行']} 行：{x['字數']} 字（上限 {res['長句上限']}）「{x['開頭']}…」")
        for x in res['偏少']:
            print(f"[偏少] {x['項目']}：{x['說明']}（只供參考）")
        print(f"共 {len(res['超出']) + len(res['長句'])} 筆需要回頭看")
    return 1 if needs_review(res) else 0


if __name__ == '__main__':
    sys.exit(main())
