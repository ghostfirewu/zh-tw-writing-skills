"""公開 repo 的個資與內部資訊檢查。用法：python3 tests/test_privacy.py（全過印 ALL PASS）

只抓「通用格式」：Windows 絕對路徑與網路路徑、個人家目錄路徑、email、
Office／PDF 檔的作者、公司與帳號欄位（PDF 只看未壓縮的 Info 字典，壓在物件串流裡的抓不到）。
具體的人名、公司或出版社名稱不能寫在這裡（這份清單本身是公開的），
請各自在推送前用本機名單自查，見 CONTRIBUTING.md。
"""
import os
import re
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
failures = []

WIN_PATH = re.compile(r'(?<![A-Za-z0-9])[A-Za-z]:(?:\\{1,2}|/)[^\s\\/]|\\\\[A-Za-z0-9._-]+\\')
HOME_PATH = re.compile(r'/(?:Users|home)/(?!user/)[A-Za-z0-9._-]+/')
EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.(?!(?:png|jpe?g|gif|svg|webp)\b)[A-Za-z]{2,}\b')
EMAIL_OK_DOMAINS = ('users.noreply.github.com', 'example.com', 'example.org')
EMAIL_OK = {'noreply@anthropic.com'}
TEXT_EXT = {'.md', '.py', '.txt', '.tsv', '.ini', '.json', '.yml', '.yaml', '.bat', '.ps1', '.sh', ''}
OFFICE_AUTHOR = re.compile(r'<(?:dc:creator|cp:lastModifiedBy|Company|Manager|author)>([^<]*)<'
                           r'|w:author="([^"]*)"|w15:author="([^"]*)"')
OFFICE_ACCOUNT = re.compile(r'w15:presenceInfo|\buserId="[^"]+"|displayName="[^"]+"|w:initials="[^"]+"')
OK_AUTHORS = {'', 'Author', 'python-docx'}


def tracked_files():
    # 已追蹤的檔，加上尚未加入版控、但沒被 .gitignore 排除的新檔
    out = subprocess.run(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
                         cwd=ROOT, capture_output=True).stdout
    files = [f for f in out.decode('utf-8').split('\0') if f]
    return files or [os.path.relpath(os.path.join(dp, f), ROOT)
                     for dp, dn, fs in os.walk(ROOT) if '.git' not in dp for f in fs]


def expect(cond, name):
    print(('  ok   ' if cond else '  FAIL ') + name)
    if not cond:
        failures.append(name)


def check_text_file(rel, text):
    probs = []
    for no, line in enumerate(text.split('\n'), 1):
        if WIN_PATH.search(line):
            probs.append(f'{rel}:{no} Windows 絕對路徑或網路路徑')
        if HOME_PATH.search(line):
            probs.append(f'{rel}:{no} 個人家目錄路徑')
        for m in EMAIL.finditer(line):
            if m.group().startswith('git@'):
                continue
            domain = m.group().split('@', 1)[1].lower()
            if m.group() in EMAIL_OK or any(domain == d or domain.endswith('.' + d) for d in EMAIL_OK_DOMAINS):
                continue
            probs.append(f'{rel}:{no} email {m.group()}')
    return probs


def check_office(rel, path):
    probs = []
    with zipfile.ZipFile(path) as z:
        for n in z.namelist():
            if not n.endswith('.xml'):
                continue
            s = z.read(n).decode('utf-8', errors='replace')
            for m in OFFICE_AUTHOR.finditer(s):
                v = next((g for g in m.groups() if g is not None), '')
                if v not in OK_AUTHORS:
                    probs.append(f'{rel} {n} 作者欄「{v}」')
            if OFFICE_ACCOUNT.search(s):
                probs.append(f'{rel} {n} 含帳號資訊（presenceInfo、userId、displayName、留言縮寫）')
    return probs


def check_pdf(rel, path):
    data = open(path, 'rb').read()
    probs = []
    for m in re.finditer(rb'/Author\s*(?:\(([^)]*)\)|<([0-9A-Fa-f]*)>)', data):
        if (m.group(1) or m.group(2) or b'').strip() not in (b'', b'FEFF', b'feff'):
            probs.append(f'{rel} PDF 作者欄')
    if re.search(rb'<dc:creator>', data):
        probs.append(f'{rel} PDF XMP 作者欄')
    return probs


def scan_repo():
    probs = []
    for rel in tracked_files():
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path) or rel.startswith('tests/test_privacy.py'):
            continue
        ext = os.path.splitext(rel)[1].lower()
        if ext in ('.docx', '.xlsx', '.pptx'):
            probs += check_office(rel, path)
        elif ext == '.pdf':
            probs += check_pdf(rel, path)
        elif ext in TEXT_EXT:
            try:
                probs += check_text_file(rel, open(path, encoding='utf-8').read())
            except UnicodeDecodeError:
                pass
    return probs


# 偵測器本身要抓得到（先證明它有牙）
expect(check_text_file('x.md', '輸出到 D:\\報表'), '偵測器：抓得到 Windows 絕對路徑')
expect(check_text_file('x.md', '寄到 someone@company.com.tw'), '偵測器：抓得到 email')
expect(not check_text_file('x.md', 'Co-Authored-By: noreply@anthropic.com'), '偵測器：放行 noreply')
expect(not check_text_file('x.md', '比例 1:2、時間 3:30'), '偵測器：一般冒號不誤報')

expect(check_text_file('x.md', '在 /Users/alice/Documents 底下'), '偵測器：抓得到 macOS 家目錄路徑')
expect(check_text_file('x.md', '在 /home/bob/work 底下'), '偵測器：抓得到 Linux 家目錄路徑')
expect(check_text_file('x.md', '放在 C:/Users/x/a.md'), '偵測器：抓得到正斜線的 Windows 路徑')
expect(check_text_file('x.md', '分享到 \\\\fileserver\\share'), '偵測器：抓得到 UNC 網路路徑')
expect(not check_text_file('x.md', 'git clone git@github.com:o/r、icon@2x.png、user@example.com'), '偵測器：不誤報 git@github.com、圖檔名、example.com')

expect(not check_text_file('x.md', 'a@sub.example.com'), '偵測器：放行 example.com 子網域')
import tempfile  # noqa: E402
_d = tempfile.mkdtemp()


def _zip(name, part, xml):
    p = os.path.join(_d, name)
    with zipfile.ZipFile(p, 'w') as z:
        z.writestr(part, xml)
    return p


expect(check_office('a.docx', _zip('a.docx', 'docProps/app.xml', '<Properties><Company>某公司</Company></Properties>')),
       '偵測器：Office app.xml 的公司欄')
expect(check_office('b.xlsx', _zip('b.xlsx', 'xl/comments1.xml', '<comments><authors><author>王小明</author></authors></comments>')),
       '偵測器：xlsx 批註作者')
expect(check_office('c.xlsx', _zip('c.xlsx', 'xl/persons/person.xml', '<person displayName="王小明" userId="abc"/>')),
       '偵測器：xlsx 討論串留言者')
expect(check_office('d.docx', _zip('d.docx', 'word/comments.xml', '<w:comment w:initials="WXM"/>')),
       '偵測器：docx 留言縮寫')
_pdf = os.path.join(_d, 'e.pdf')
open(_pdf, 'wb').write(b'%PDF-1.4\n1 0 obj << /Author <FEFF738B5C0F660E> >> endobj')
expect(check_pdf('e.pdf', _pdf), '偵測器：PDF 十六進位作者欄')

probs = scan_repo()
for p in probs:
    print('       ' + p)
expect(not probs, f'全 repo 沒有個資或內部路徑（{len(probs)} 筆）')

print()
if failures:
    print(f'{len(failures)} 項失敗')
    sys.exit(1)
print('ALL PASS')
