"""zh-tw-anti-slop 掃描器的驗收測試。用法：python3 tests/test_slop_scan.py（全過印 ALL PASS）"""
import os
import sys
import importlib.util

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.environ.get('SLOP_SCAN', os.path.join(ROOT, 'skills', 'zh-tw-anti-slop', 'scripts', 'slop_scan.py'))
spec = importlib.util.spec_from_file_location('slop_scan', SCRIPT)
ss = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ss)
failures = []


def expect(cond, name):
    print(('  ok   ' if cond else '  FAIL ') + name)
    if not cond:
        failures.append(name)


def cats(text):
    return [h['category'] for h in ss.scan(text)]


def found(text):
    return [h['match'] for h in ss.scan(text)]


pats = ss.load_patterns()
expect(len(pats) >= 80, f'詞表載入 {len(pats)} 條（≥80）')

expect(found('我們要賦能每一位創作者') == ['賦能'], '字面詞：賦能')
expect(found('值得注意的是，價格漲了') == ['值得注意的是'], '墊片詞：值得注意的是')
expect(any(c == '二元對比' for c in cats('筆記不僅僅是紀錄，它更是思考的延伸')), '正規式：不僅僅是…更是')
expect(any(c == '開場白套路' for c in cats('在現今瞬息萬變的數位時代中，我們…')), '正規式：在現今…時代')
expect(found('團隊進行調查後發現') == ['進行調查'], '翻譯腔：進行調查')
expect(found('希望對你有幫助！') == ['希望對你有幫助'], '聊天殘渣：希望對你有幫助')
expect(found('作為AI，我無法') == ['作為AI'], '聊天殘渣：作為AI')
expect(found('看 https://x.com/a?utm_source=chatgpt.com 這篇') == ['utm_source=chatgpt.com'], '工具痕跡：utm_source')
expect(found('請洽 [品牌名稱] 客服') == ['[品牌名稱]'], '佔位符殘留')
expect(any(c == '假洞見・冒號揭曉' for c in cats('最妙的是：它免費')), '冒號揭曉')

# 不誤報
expect(found('上週六來了 80 個人，比去年多一倍。') == [], '具體敘述不報')
expect(found('這篇說明三個設定步驟。') == [], '一般句子不報')

# 程式碼不掃
md = '正文賦能\n```\nx = "賦能"\n```\n行內 `賦能` 不算'
expect([h['line'] for h in ss.scan(md)] == [1], '程式碼區塊與行內程式碼不掃')

# 同一段文字只報一次
expect(len(ss.scan('作為AI')) == 1, '重疊樣式只報一次')

# 欄位位置正確
h = ss.scan('第一行\n這裡有個痛點')[0]
expect((h['line'], h['col']) == (2, 5), '行、欄位置正確（2:5）')

# v1.1 新增樣式
expect('擬人・物件當主詞' in cats('數據告訴我們一件事'), '擬人：數據告訴我們')
expect('句尾綴掛評論' in cats('他把配方改了三次，凸顯了品管的重要性'), '句尾綴掛評論')
expect(cats('他把配方改了三次，良率從六成升到九成') == [], '尾巴帶新事實不報')
expect('模糊歸因' in cats('研究顯示睡眠很重要'), '模糊歸因：研究顯示')
expect(cats('他的研究顯示睡眠很重要（Smith, 2010）') == [], '有出處（作者—年份）不報')
expect(cats('我在調查顯示器的問題') == [], '「調查顯示器」不誤報')
expect('翻譯腔・框式介詞' in cats('在學習對位法的過程中，學生常卡關'), '框式介詞')
expect('AI 工具標記殘留' in cats('見前文[cite: 1, 3]'), 'AI 工具標記：[cite: N]')
expect('強制昇華結尾' in cats('儘管仍面臨不少挑戰，但前景可期'), '強制昇華結尾')
sug = {h['category']: h['advice'] for h in ss.scan('筆記不僅僅是紀錄，它更是思考的延伸')}
expect('稻草人' in sug.get('二元對比', ''), '二元對比的改寫方向含保留判準')

# Markdown 粗體失效（判定與 CommonMark／GitHub 一致；開發時以 markdown-it-py 隨機交叉驗證過）
def bold_cols(text):
    return [h['col'] for h in ss.scan(text) if h['category'] == 'Markdown・粗體失效']


expect(bold_cols('接著**「文書」**再') == [3, 9], '括號包進粗體、兩側貼字 → 兩個 ** 都失效')
expect(bold_cols('請先決定「**文書的立場**」') == [], '只包括號內側 → 正常')
expect(bold_cols('這是**必須。**詳見下文') != [], '句末標點包進粗體、後面貼字 → 失效')
expect(bold_cols('這是**必須**。詳見下文') == [], '標點移到外面 → 正常')
expect(bold_cols('立場用 **「建議」或「規定」** 決定') == [], '外側加半形空格 → 正常')
expect(bold_cols('一般的**粗體**文字') == [], '中文字之間的粗體 → 正常')
expect(bold_cols('```\n用**「x」**寫\n```') == [], '程式碼區塊內不查')
expect(bold_cols('行內 `a**「x」**b` 不查') == [], '行內程式碼內不查')
expect(bold_cols('這是一段**跨行的\n粗體**文字') == [], '跨行的粗體正常配對，不誤報')
expect(cats('據衛福部 2023 年調查顯示，國人睡眠不足') == [], '前面已有出處（2023 年調查）不報')
expect(cats('研究顯示睡眠很重要[^1]') == [], '後面有註腳標記不報')
expect(cats('學界普遍認為（見陳，2019）這是主因') == [], '學界普遍認為＋（年份出處）不報')
expect(cats('研究顯示睡眠很重要。[^1]') == [], '註腳在句號後面也不報')
expect(cats('業界普遍認為這是主因[^2]') == [], '業界普遍認為＋註腳不報')
expect(cats('有專家指出（王，2020）這是主因') == [], '有專家指出＋（年份出處）不報')
expect(cats('歷史告訴我們，戰爭沒有贏家') == [], '「歷史告訴我們」是 AI 普及前常見說法，不報')
for k in ('重要的是要記住', '我們必須認識到', '不可忽視的是', '值得注意的是'):
    adv = {h['category']: h['advice'] for h in ss.scan(k + '，備份要先做')}
    expect('評價' in adv.get('墊片詞・假嚴謹', ''), f'「{k}」的改寫方向含「評價要留下來」')
expect(bold_cols('>>> [(x, x**2) for x in range(6)]') == [], '次方運算 x**2 不報（不貼中文）')
expect(bold_cols('>>> 5 ** 2  # 5 的平方') == [], '次方運算 5 ** 2 不報')

# 跨詞誤判：「好問題」不能命中「偏好＋問題」
expect(found('要不要用，是個人風險偏好問題') == [], '好問題：不誤報「偏好問題」')
expect(found('好問題！我們先看預算') == ['好問題'], '好問題：開場諂媚照報')

print()
if failures:
    print(f'{len(failures)} 項失敗')
    sys.exit(1)
print('ALL PASS')
