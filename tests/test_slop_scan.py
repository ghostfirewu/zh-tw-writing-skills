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

print()
if failures:
    print(f'{len(failures)} 項失敗')
    sys.exit(1)
print('ALL PASS')
