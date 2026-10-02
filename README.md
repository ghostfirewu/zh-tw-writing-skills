# zh-tw-writing-skills

繁體中文（台灣）寫作與編輯用的 AI agent skill。三支 skill 加一支 hook，針對 AI 寫繁中最常出的問題：簡體字殘留、中國用語、AI 腔，以及出版編輯的書稿檢查。

| Skill | 做什麼 | 例 |
|---|---|---|
| [`zh-tw-guard`](skills/zh-tw-guard/SKILL.md) | 繁中守門：簡體字、一簡多繁、錯轉繁、中國用語 | 这个→這個、以后→以後、頭發→頭髮、視頻→影片；「申請程序」「質量守恆」**不改** |
| [`zh-tw-anti-slop`](skills/zh-tw-anti-slop/SKILL.md) | 去 AI 腔：灌水詞、墊片詞、二元對比、翻譯腔、聊天殘渣 | 「X 不僅僅是 Y，它更是 Z」→ 直接講 Z；「進行調查」→「調查」 |
| [`manuscript-check`](skills/manuscript-check/SKILL.md) | 書稿規則式檢查（不用 AI）：Word 稿健檢、定稿與排版 PDF 逐字比對、索引頁碼 | 標點不成對、圖表編號跳號、引用與書目對不上、排版漏段 |

**Hook**（僅 Claude Code）：每次 Write／Edit 寫入新內容後，自動掃簡體字、一簡多繁、錯轉繁，有命中就提醒 Claude 修正。只提醒、不擋寫入；路徑含 `zh-CN`、`zh_Hans`、`zh-SG` 這類簡體在地化標記的檔案自動跳過。

## 安裝

### Claude Code（建議，含 hook）

```
/plugin marketplace add ghostfirewu/zh-tw-writing-skills
/plugin install zh-tw-writing@zh-tw-writing-skills
```

裝好後 skill 以 `/zh-tw-writing:zh-tw-guard` 這類名稱出現，Claude 也會在相關任務自動使用。要暫時關掉 hook，設環境變數 `ZHTW_GUARD_OFF=1`。

### 其他支援 SKILL.md 的工具（claude.ai、其他 agent）

每個 `skills/<名稱>/` 資料夾都是獨立的 skill，可以單獨取用：複製到該工具的 skills 目錄，或壓成 zip 上傳。腳本需要能執行 Python 的環境；hook 只在 Claude Code 有效。

## 需求

- **Python 3.8 以上**。`zh-tw-guard`、`zh-tw-anti-slop` 的腳本只用標準函式庫。
- `manuscript-check` 另需四個套件：
  ```
  pip install -r skills/manuscript-check/scripts/requirements.txt
  ```
- Hook 用 `sh` 啟動 Python（先找 `python3`，再找 `python`）。Windows 上的 Claude Code 透過 Git Bash 執行 hook；若系統只有 Microsoft Store 的 Python 空殼，hook 會無聲略過，不影響寫檔。

## 腳本也可以單獨用

```bash
# 繁中守門：有簡體或 A 級中國用語時結束代碼為 1，可接 CI
python3 skills/zh-tw-guard/scripts/zhtw_check.py 文章.md
python3 skills/zh-tw-guard/scripts/zhtw_check.py --level A docs/*.md

# AI 腔候選
python3 skills/zh-tw-anti-slop/scripts/slop_scan.py 貼文.txt
python3 skills/zh-tw-anti-slop/scripts/slop_scan.py --summary 第*.md

# 書稿健檢（輸出 Excel 報表）
cd skills/manuscript-check/scripts
python3 稿件健檢.py 書稿.docx
```

掃描器列的都是**候選**。中國用語分兩級：A 級（視頻、軟件）可以直接換；B 級（程序、質量、支持）在台灣也有正常用法，要看語境判斷，對照表寫了每個詞的保留語境。

## 測試

```bash
python3 tests/run_all.py
```

六組測試：守門掃描器、AI 腔掃描器、hook、書稿健檢、排版比對、索引頁碼。GitHub Actions 在 Linux、Windows、macOS 上跑。

## 貢獻

詞表是最需要補的部分：

- 中國用語：`skills/zh-tw-guard/data/terms.tsv` 加一列，並在 `skills/zh-tw-guard/references/terms.md` 對應的表補上同一個詞（測試會檢查兩邊一致）。B 級詞請附保留語境和排除詞。
- 一簡多繁、錯轉繁：`skills/zh-tw-guard/data/` 的兩個清單，同步改 `skills/manuscript-check/scripts/設定/` 的同名檔（測試會檢查兩份一致）。
- AI 腔：`skills/zh-tw-anti-slop/data/slop.tsv`。

改完跑 `python3 tests/run_all.py`。

## 授權

- 程式碼：[MIT](LICENSE)
- 規則文字與詞表（`SKILL.md`、`references/`、`data/`、`設定/` 的清單、說明文件）：[CC BY 4.0](LICENSE-CONTENT.md)
- `skills/manuscript-check/scripts/data/筆畫表.tsv`：取自 [Unicode Unihan Database](https://www.unicode.org/charts/unihan.html)，依 Unicode License v3 轉載（授權全文見同資料夾的 `LICENSE-UNICODE.txt`）

## 致謝

中國用語對照表的部分詞條參考了社群整理的支語與 OpenCC 轉換殘留清單（acchuang、voice-guard、aeopress），再逐詞補上台灣語境的保留規則。
