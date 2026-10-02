#!/usr/bin/env python3
"""PostToolUse hook（Write|Edit|MultiEdit）：寫進檔案的新內容若有簡體殘留、一簡多繁、錯轉繁，就提醒 Claude。

偵測不阻擋：檔案已經寫入，exit 2 只是把 stderr 餵回 Claude，讓它自己改正。
只查高準確度的三類（簡體、一簡多繁、錯轉）；中國用語要看語境，留給 /zh-tw-guard skill 判斷。
跳過：路徑含 zh-CN、zh_CN、zhcn、zh-Hans、zh-SG、zh-MY（不分大小寫）的簡體在地化檔；設了環境變數 ZHTW_GUARD_OFF=1。
任何解析失敗一律放行（exit 0），不干擾正常寫檔。
"""
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKER = os.path.join(os.path.dirname(HERE), 'skills', 'zh-tw-guard', 'scripts', 'zhtw_check.py')
SKIP_PATH = re.compile(r'zh[-_]?(cn|hans|sg|my)(?![a-z])', re.I)
MAX_REPORT = 15


def new_text(tool_input):
    """取出這次寫入的新內容：Write 的 content、Edit 的 new_string、MultiEdit 的 edits[].new_string。"""
    parts = []
    for key in ('content', 'file_contents', 'new_string'):
        v = tool_input.get(key)
        if isinstance(v, str):
            parts.append(v)
    for e in tool_input.get('edits') or []:
        if isinstance(e, dict) and isinstance(e.get('new_string'), str):
            parts.append(e['new_string'])
    return '\n'.join(parts)


def main():
    if os.environ.get('ZHTW_GUARD_OFF') == '1':
        return 0
    try:
        raw = sys.stdin.buffer.read().decode('utf-8', errors='replace').lstrip('﻿')
        data = json.loads(raw or '{}')
        tool_input = data.get('tool_input') or {}
        path = str(tool_input.get('file_path') or '')
        if SKIP_PATH.search(path):
            return 0
        text = new_text(tool_input)
        if not text:
            return 0
        spec = importlib.util.spec_from_file_location('zhtw_check', CHECKER)
        zc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(zc)
        hits = zc.check_text(text, only=('簡體', '一簡多繁', '錯轉'))
    except Exception:
        return 0
    if not hits:
        return 0
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        pass
    lines = text.split('\n')
    out = [f'[zh-tw-guard] {os.path.basename(path) or "剛寫入的內容"} 有 {len(hits)} 處疑似簡體殘留，請逐一確認並改成正體：']
    for h in hits[:MAX_REPORT]:
        ctx = lines[h['line'] - 1].strip()
        if len(ctx) > 40:
            c = h['col'] - 1 - (len(lines[h['line'] - 1]) - len(lines[h['line'] - 1].lstrip()))
            ctx = '…' + ctx[max(0, c - 15):c + 15] + '…'
        out.append(f"  - [{h['category']}] {h['match']}　（{ctx}）")
    if len(hits) > MAX_REPORT:
        out.append(f'  …另有 {len(hits) - MAX_REPORT} 處')
    out.append('地名、日本人名、引用原文可能是誤報，確認是刻意保留的就不用改。')
    sys.stderr.write('\n'.join(out) + '\n')
    return 2


if __name__ == '__main__':
    sys.exit(main())
