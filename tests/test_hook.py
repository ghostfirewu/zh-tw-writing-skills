"""hooks/zhtw_post_write.py 的驗收測試。用法：python3 tests/test_hook.py（全過印 ALL PASS）"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.environ.get('ZHTW_HOOK', os.path.join(ROOT, 'hooks', 'zhtw_post_write.py'))
failures = []


def run(payload, env_extra=None):
    env = dict(os.environ)
    env.pop('ZHTW_GUARD_OFF', None)
    env.update(env_extra or {})
    raw = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode('utf-8')
    p = subprocess.run([sys.executable, HOOK], input=raw, capture_output=True, env=env)
    return p.returncode, p.stderr.decode('utf-8', errors='replace')


def expect(cond, name):
    print(('  ok   ' if cond else '  FAIL ') + name)
    if not cond:
        failures.append(name)


code, err = run({'tool_name': 'Write', 'tool_input': {'file_path': '/p/a.md', 'content': '我們以后再說这个'}})
expect(code == 2 and '以后' in err and '这' in err, 'Write 有簡體 → exit 2，stderr 列出命中')

code, _ = run({'tool_name': 'Write', 'tool_input': {'file_path': '/p/a.md', 'content': '我們以後再說這個'}})
expect(code == 0, 'Write 全正體 → exit 0')

code, err = run({'tool_name': 'Edit', 'tool_input': {'file_path': '/p/a.md', 'old_string': '這', 'new_string': '头發'}})
expect(code == 2 and '头' in err, 'Edit 只查 new_string')

code, _ = run({'tool_name': 'Edit', 'tool_input': {'file_path': '/p/a.md', 'old_string': '这里', 'new_string': '這裡'}})
expect(code == 0, 'Edit 的 old_string 有簡體不算（那是被改掉的內容）')

code, err = run({'tool_name': 'MultiEdit', 'tool_input': {'file_path': '/p/a.md', 'edits': [
    {'old_string': 'a', 'new_string': '正常'}, {'old_string': 'b', 'new_string': '关系'}]}})
expect(code == 2 and '关' in err, 'MultiEdit 查每一筆 new_string')

code, _ = run({'tool_name': 'Write', 'tool_input': {'file_path': '/p/视频.md', 'content': '影片'}})
expect(code == 0, '只查內容，不查路徑')

code, _ = run({'tool_name': 'Write', 'tool_input': {'file_path': '/p/locales/zh-CN.json', 'content': '这个'}})
expect(code == 0, '簡體在地化檔（zh-CN）跳過')

code, _ = run({'tool_name': 'Write', 'tool_input': {'file_path': '/p/dataset_simplified_notes.md', 'content': '这个'}})
expect(code == 2, '檔名含 simplified 但不是在地化標記 → 照查')

code, _ = run({'tool_name': 'Write', 'tool_input': {'file_path': '/p/zh-Hant/a.md', 'content': '这个'}})
expect(code == 2, 'zh-Hant（繁體）路徑照查')

code, _ = run({'tool_name': 'Write', 'tool_input': {'file_path': '/p/a.md', 'content': '这个'}}, {'ZHTW_GUARD_OFF': '1'})
expect(code == 0, 'ZHTW_GUARD_OFF=1 關閉')

code, _ = run({'tool_name': 'Write', 'tool_input': {'file_path': '/p/a.md', 'content': '視頻很多'}})
expect(code == 0, '中國用語不在 hook 範圍（留給 skill 看語境）')

code, _ = run(b'not json')
expect(code == 0, '壞 JSON 放行')

code, _ = run('﻿{"tool_input": {"file_path": "a", "content": "这"}}'.encode('utf-8'))
expect(code == 2, '前置 BOM 的 JSON 照常解析')

print()
if failures:
    print(f'{len(failures)} 項失敗')
    sys.exit(1)
print('ALL PASS')
