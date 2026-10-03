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
    env.pop('ZHTW_WRITING_DIR', None)
    env.pop('CLAUDE_PROJECT_DIR', None)
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

code, _ = run('\ufeff{"tool_input": {"file_path": "a", "content": "这"}}'.encode('utf-8'))
expect(code == 2, '前置 BOM 的 JSON 照常解析')

# ---- hooks/run.sh 選 Python 的方式 ----
# Windows 的 python3／python 常是 Microsoft Store 的空殼別名：`command -v` 找得到，執行卻只印錯誤。
# run.sh 要實際跑得起來才採用，跑不起來就換下一個；都不行就安靜放行（exit 0），不在每次寫檔時報錯。
import shutil  # noqa: E402
import stat  # noqa: E402
import tempfile  # noqa: E402

SH = shutil.which('sh')
RUN_SH = os.path.join(ROOT, 'hooks', 'run.sh')


def stub(dirpath, name, body):
    p = os.path.join(dirpath, name)
    with open(p, 'w', encoding='utf-8', newline='\n') as f:
        f.write('#!/bin/sh\n' + body + '\n')
    os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def run_sh(stubs, payload):
    with tempfile.TemporaryDirectory() as d:
        for name, body in stubs.items():
            stub(d, name, body)
        env = dict(os.environ)
        for k in ('ZHTW_GUARD_OFF', 'ZHTW_WRITING_DIR', 'CLAUDE_PROJECT_DIR'):
            env.pop(k, None)
        env['PATH'] = d + os.pathsep + env.get('PATH', '')
        raw = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        p = subprocess.run([SH, RUN_SH], input=raw, capture_output=True, env=env)
        return p.returncode, p.stderr.decode('utf-8', errors='replace')


if SH is None:
    print('  skip run.sh 測試（找不到 sh）')
else:
    real = sys.executable.replace('\\', '/')
    broken = 'echo "Python was not found" >&2; exit 9009'
    working = f'exec "{real}" "$@"'
    simp = {'tool_name': 'Write', 'tool_input': {'file_path': '/p/a.md', 'content': '这个'}}

    code, err = run_sh({'python3': broken, 'python': working}, simp)
    expect(code == 2 and '这' in err, 'run.sh：python3 是跑不動的空殼 → 改用 python，照常提醒')

    code, err = run_sh({'python3': broken, 'python': broken}, simp)
    expect(code == 0 and 'not found' not in err, 'run.sh：兩個都跑不動 → 安靜放行，不把錯誤丟給使用者')

    code, err = run_sh({'python3': working}, simp)
    expect(code == 2 and '这' in err, 'run.sh：python3 正常 → 照常提醒（探測不吃掉 stdin）')

print()
if failures:
    print(f'{len(failures)} 項失敗')
    sys.exit(1)
print('ALL PASS')
