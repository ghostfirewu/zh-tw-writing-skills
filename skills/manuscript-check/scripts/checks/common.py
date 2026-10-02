"""各檢查共用的資料結構與小工具。"""
import configparser
import os
import re
from dataclasses import dataclass, field

# 中日韓漢字（含擴充 A 與相容區）；擴充 B 以後在 Python 字串裡是單一字元，另列
CJK = r'㐀-䶿一-鿿豈-﫿\U00020000-\U0003134f'
CJK_RE = re.compile(f'[{CJK}]')


def is_cjk(ch):
    return bool(CJK_RE.fullmatch(ch))


@dataclass
class Hit:
    category: str      # 分類（報表的「分類」欄）
    para: object       # docx_text.Para
    match: str         # 命中的字串
    start: int = -1    # 在段落中的位置；-1 表示整段或全書
    end: int = -1
    note: str = ''     # 說明

    def context(self, width=18):
        t = self.para.text if self.para else ''
        if self.start < 0 or not t:
            return t[:width * 3]
        a = max(0, self.start - width)
        b = min(len(t), self.end + width)
        return ('…' if a > 0 else '') + t[a:self.start] + '【' + t[self.start:self.end] + '】' + t[self.end:b] + ('…' if b < len(t) else '')


@dataclass
class Result:
    title: str                                 # 工作表名稱
    hits: list = field(default_factory=list)
    notes: list = field(default_factory=list)  # 寫進總覽的備註（例：本項未執行的原因）
    table: list = None                         # 另附的表格（第一列為表頭）
    table_title: str = ''                      # 另附表格的工作表名稱
    header: list = None                        # 自訂明細欄位（有設定時，明細表改用 rows 而不是 hits）
    rows: list = None


def load_config(path):
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.optionxform = str
    with open(path, encoding='utf-8-sig') as f:
        cfg.read_file(f)
    base = os.path.dirname(os.path.abspath(path))
    # 設定檔裡的相對路徑一律以設定檔所在資料夾為準
    for sec in cfg.sections():
        for k, v in cfg[sec].items():
            if k.endswith(('表', '清單', '名單')) and v:
                # 可用 | 分隔多個檔案
                parts = [x.strip() for x in v.split('|') if x.strip()]
                cfg[sec][k] = '|'.join(x if os.path.isabs(x) else os.path.normpath(os.path.join(base, x)) for x in parts)
    return cfg


def read_lines(path):
    """讀 UTF-8 文字清單：略過空行與以 ' 或 # 開頭的註解行。"""
    if not path or not os.path.exists(path):
        return []
    with open(path, encoding='utf-8-sig') as f:
        return [ln.rstrip('\r\n') for ln in f if ln.strip() and not ln.startswith(("'", '#'))]


def parse_token(s):
    """「U+F900」寫法轉成字元，其餘照原樣（詞表裡看不出差別的字可用碼位寫）。"""
    m = re.fullmatch(r'[Uu]\+([0-9A-Fa-f]{4,6})', s)
    return chr(int(m.group(1), 16)) if m else s


def covered(text, start, end, words):
    """text[start:end] 是否落在 words 裡某個詞的出現範圍內（用來排除「若干部分」這類跨詞界誤報）。"""
    for w in words:
        i = text.find(w, max(0, end - len(w)))
        while 0 <= i <= start:
            if i + len(w) >= end:
                return True
            i = text.find(w, i + 1)
    return False


def finditer_all(pattern, doc, parts=None):
    """對每一段跑 re.finditer，產生 (段落, match)。"""
    rx = re.compile(pattern) if isinstance(pattern, str) else pattern
    for p in doc.paras:
        if parts and p.part not in parts:
            continue
        for m in rx.finditer(p.text):
            yield p, m
