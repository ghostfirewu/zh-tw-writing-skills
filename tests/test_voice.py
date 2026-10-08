"""zh-tw-voice 兩支腳本的驗收測試。用法：python3 tests/test_voice.py（全過印 ALL PASS）

例句全是虛構的，不取自任何真實貼文。
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, 'skills', 'zh-tw-voice', 'scripts')
PROFILE = os.path.join(SCRIPTS, 'voice_profile.py')
CHECK = os.path.join(SCRIPTS, 'voice_check.py')
failures = []


def expect(cond, name):
    print(('  ok   ' if cond else '  FAIL ') + name)
    if not cond:
        failures.append(name)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(script, *args, cwd=None, env=None):
    e = dict(os.environ, PYTHONIOENCODING='utf-8')
    for k in ('ZHTW_WRITING_DIR', 'CLAUDE_PROJECT_DIR'):
        e.pop(k, None)
    e.update(env or {})
    p = subprocess.run([sys.executable, script] + list(args), capture_output=True, cwd=cwd, env=e)
    return p.returncode, p.stdout.decode('utf-8'), p.stderr.decode('utf-8')


vp = load(PROFILE, 'voice_profile')
vc = load(CHECK, 'voice_check')

# ── 語氣詞與標點的計數 ──
c = vp.counts('今天好累啦，不過還是去了吧。欸，你有看到嗎？')
expect(c['語氣詞'] == 3, f"語氣詞：啦、吧、欸各算一次（得到 {c['語氣詞']}）")
c = vp.counts('我們在酒吧。吧台很長，耶穌像在牆上。')
expect(c['語氣詞'] == 0, f"字面義不算語氣詞：酒吧、吧台、耶穌（得到 {c['語氣詞']}）")
c = vp.counts('真的假的！！這也太扯了吧……然後——就沒有然後了～')
expect(c['驚嘆號'] == 2 and c['刪節號'] == 1 and c['破折號'] == 1 and c['波浪號'] == 1,
       f'標點：驚嘆號 2、刪節號 1、破折號 1、波浪號 1（得到 {c}）')
c = vp.counts('今天天氣很好 😀 出門走走 ☀')
expect(c['emoji'] == 2, f"emoji 計數（得到 {c['emoji']}）")
c = vp.counts('程式碼不算：`好啦！`\n```\n真的啦！！\n```\n正文。')
expect(c['語氣詞'] == 0 and c['驚嘆號'] == 0, '程式碼區塊與行內程式碼不計')

# ── 句長與長句 ──
s = vp.sentences('第一句很短。第二句也短！\n\n第三句？')
expect([len(x) for x in s] == [5, 5, 3], f'斷句：句號、驚嘆號、問號、換行（得到 {s}）')
long_line = '這個計畫' + '，然後我們又' * 15 + '。短句。'
lng = vc.long_sentences(long_line, 80)
expect(len(lng) == 1 and lng[0]['字數'] > 80, '一逗到底的長句被抓出來')

# ── 建檔 ──
d = tempfile.mkdtemp()
casual = '欸今天去吃那家拉麵啦，排了超久～不過真的好吃！！下次再來吧。\n\n老闆人超好，還多給一顆蛋 😆\n'
samples = []
for i in range(6):
    p = os.path.join(d, f's{i}.md')
    open(p, 'w', encoding='utf-8').write(casual * 12)
    samples.append(p)
prof = vp.build([open(p, encoding='utf-8').read() for p in samples], names=samples)
expect(prof['樣本']['篇數'] == 6 and prof['樣本']['信心'] == '足夠', f"樣本足夠（{prof['樣本']}）")
expect(prof['每千字']['語氣詞'] > 0 and prof['每千字']['emoji'] > 0, '每千字的語氣詞、emoji 有算出來')
expect(set(prof['句長']) >= {'p25', '中位數', 'p75'}, '句長有 p25、中位數、p75')
expect(prof['長句上限'] >= 60, '長句上限有預設值')
small = vp.build(['只有一篇短文。'], names=['a.md'])
expect(small['樣本']['信心'] == '低', '樣本太少 → 信心低')

phrase_doc = '說真的，這件事很難。' + '今天天氣不錯，我們去散步，順便買了晚餐。' * 5
prof2 = vp.build([phrase_doc] * 6, names=list('abcdef'), phrases=['說真的'])
expect(prof2['口頭禪'].get('說真的', 0) > 0, '指定的口頭禪會算出每千字頻率')

# 樣本若 AI 腔很重，標「疑似」，但不自動排除
slop_text = '在現今瞬息萬變的數位時代中，這款工具無疑為創作者賦能，打造全新的契機。值得注意的是，它更是一種底層邏輯。'
prof3 = vp.build([slop_text, casual * 12], names=['ai.md', 'me.md'])
marks = {x['檔名']: x for x in prof3['樣本明細']}
if vp.slop_available():
    expect(marks['ai.md']['疑似AI腔'] and not marks['me.md']['疑似AI腔'], 'AI 腔重的樣本標成疑似，正常的不標')
else:
    print('  skip 找不到 zh-tw-anti-slop，略過 AI 腔密度測試')
expect(prof3['樣本']['篇數'] == 2, '疑似的樣本不自動排除')

# --split：單一檔案用 --- 分篇
one = os.path.join(d, 'threads.md')
open(one, 'w', encoding='utf-8').write('第一篇。\n---\n第二篇。\n---\n第三篇。\n')
rc, out, err = run(PROFILE, '--split', '--json', one)
expect(rc == 0 and json.loads(out)['樣本']['篇數'] == 3, f'--split 以 --- 分篇（rc={rc} {err}）')

# --out 寫出 voice.json
cfg = os.path.join(d, 'proj', '.zh-tw-writing')
os.makedirs(cfg)
rc, out, err = run(PROFILE, '--out', os.path.join(cfg, 'voice.json'), *samples)
saved = json.load(open(os.path.join(cfg, 'voice.json'), encoding='utf-8'))
expect(rc == 0 and saved['樣本']['篇數'] == 6, '--out 寫出 voice.json')
expect(all(os.sep not in x['檔名'] and '/' not in x['檔名'] for x in saved['樣本明細']),
       'voice.json 只存檔名，不存路徑')
rc, out, err = run(PROFILE, os.path.join(d, 'none.md'))
expect(rc == 2, '樣本檔不存在 → 結束代碼 2')

# ── 成品對照：社群 ──
ok_draft = '欸今天去了那家咖啡店啦，人有點多～不過拿鐵很好喝！下次再來吧。'
r = vc.check(ok_draft, saved, '社群')
expect(not r['超出'] and not r['長句'], f'社群：頻率在習慣範圍內 → 不報（{r}）')
over = '好啦好啦！！！真的啦～～太好吃了啦！！欸欸欸！！😆😆😆😆'
r = vc.check(over, saved, '社群')
expect(any(x['項目'] == '語氣詞' for x in r['超出']), '社群：語氣詞用得比習慣多太多 → 超出')
flat = '今天去了那家咖啡店。人有點多，拿鐵很好喝，下次會再來。店內座位不多，建議避開中午。' * 3
r = vc.check(flat, saved, '社群')
expect(not r['超出'] and any(x['項目'] == '語氣詞' for x in r['偏少']), '社群：完全沒有語氣詞 → 只列偏少，不算超出')
r = vc.check('說真的，說真的，說真的，這很難。', prof2, '社群')
expect(any(x['項目'] == '口頭禪：說真的' for x in r['超出']), '社群：口頭禪塞太多 → 超出')

# ── 成品對照：正式 ──
r = vc.check('本季營收成長，主因是新客戶增加啦！', saved, '正式')
items = {x['項目'] for x in r['超出']}
expect('語氣詞' in items and '驚嘆號' in items, f'正式：口語語氣詞與驚嘆號一出現就報（{items}）')
r = vc.check('本季營收成長，主因是新客戶增加。下季將持續追蹤。', saved, '正式')
expect(not r['超出'] and not r['偏少'], '正式：沒有口語特徵 → 不報，也不列偏少')
r = vc.check('本季營收成長，主因是新客戶增加。', None, '正式')
expect(not r['超出'], '正式：沒有風格檔也能跑')

# ── 命令列 ──
draft = os.path.join(d, 'draft.md')
open(draft, 'w', encoding='utf-8').write(over)
rc, out, err = run(CHECK, '--register', '社群', draft, cwd=os.path.join(d, 'proj'))
expect(rc == 1 and '語氣詞' in out, f'CLI：自動找到 .zh-tw-writing/voice.json，超出 → 1（rc={rc} {err}）')
open(draft, 'w', encoding='utf-8').write(ok_draft)
rc, out, err = run(CHECK, '--register', '社群', draft, cwd=os.path.join(d, 'proj'))
expect(rc == 0, f'CLI：在習慣範圍內 → 0（rc={rc} {out}{err}）')
rc, out, err = run(CHECK, '--register', '社群', draft, cwd=d)
expect(rc == 2, '社群模式找不到風格檔 → 結束代碼 2')
rc, out, err = run(CHECK, '--register', '正式', draft, cwd=d)
expect(rc == 1, '正式模式沒有風格檔也能跑（草稿有口語特徵 → 1）')
rc, out, err = run(CHECK, '--register', '社群', '--json', draft, cwd=os.path.join(d, 'proj'))
expect(rc == 0 and set(json.loads(out)) >= {'場合', '字數', '超出', '偏少', '長句'}, 'CLI：--json 欄位')
rc, out, err = run(CHECK, '--register', '社群', '--config-dir', os.path.join(d, 'nope'), draft)
expect(rc == 2, '--config-dir 指到不存在的路徑 → 2')
rc, out, err = run(CHECK, '--register', '社群', '--profile', os.path.join(cfg, 'voice.json'), draft, cwd=d)
expect(rc == 0, '--profile 直接指定風格檔')
rc, out, err = run(CHECK, '--register', '社群', draft, cwd=d, env={'ZHTW_WRITING_DIR': cfg})
expect(rc == 0, '環境變數 ZHTW_WRITING_DIR 也找得到風格檔')

print()
if failures:
    print(f'{len(failures)} 項失敗')
    sys.exit(1)
print('ALL PASS')
