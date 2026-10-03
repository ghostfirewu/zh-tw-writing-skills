#!/usr/bin/env python3
"""從 CHANGELOG.md 取出某一版的說明，給自動建立 GitHub Release 用。

用法：python3 .github/scripts/changelog_section.py 1.2.1 [CHANGELOG.md]
印出「## v1.2.1」到下一個「## v」之間的內容；找不到或內容是空的，結束代碼 1。
"""
import os
import re
import sys


def section(text, version):
    m = re.search(r'^## v' + re.escape(version) + r'[ \t]*$(.*?)(?=^## v|\Z)', text, re.M | re.S)
    return m.group(1).strip() if m else ''


def main(argv):
    if len(argv) < 2:
        print('用法：changelog_section.py 版本號 [CHANGELOG.md]', file=sys.stderr)
        return 2
    path = argv[2] if len(argv) > 2 else os.path.join(os.path.dirname(__file__), '..', '..', 'CHANGELOG.md')
    with open(path, encoding='utf-8') as f:
        body = section(f.read(), argv[1].lstrip('v'))
    if not body:
        print(f'CHANGELOG.md 找不到 v{argv[1].lstrip("v")} 的內容', file=sys.stderr)
        return 1
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        pass
    print(body)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
