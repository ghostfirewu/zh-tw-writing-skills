# zh-tw-writing-skills

繁體中文（台灣）寫作與編輯用的 AI agent skill。四支 skill 加一支 hook，針對 AI 寫繁中最常出的問題：簡體字殘留、中國用語、AI 腔，以及出版編輯的書稿檢查；另有選用的個人口吻模組。

| Skill | 做什麼 | 例 |
|---|---|---|
| [`zh-tw-guard`](skills/zh-tw-guard/SKILL.md) | 繁中守門：簡體字、一簡多繁、錯轉繁、中國用語 | 这个→這個、以后→以後、頭發→頭髮、視頻→影片；「申請程序」「質量守恆」**不改** |
| [`zh-tw-anti-slop`](skills/zh-tw-anti-slop/SKILL.md) | 去 AI 腔：灌水詞、墊片詞、二元對比、翻譯腔、擬人、強制昇華結尾、聊天殘渣、Markdown 排版痕跡；並守住改寫紀律（不加料、不改語氣強度、不改過頭） | 「數據告訴我們」→「從數據看得出」；「在學習的過程中」→「學習時」；改寫後多出原文沒有的數字會被比對腳本抓出來 |
| [`zh-tw-voice`](skills/zh-tw-voice/SKILL.md)（選用） | 個人口吻：動筆前先訪談作者要具體內容；從使用者自己的貼文萃取寫作習慣存成風格檔，社群貼文照習慣寫，正式文案只保留身分特徵、收掉口語並補強結構 | 作者平常每千字 3 個語氣詞，草稿寫到 10 個會被對照腳本抓出來；報告裡出現「啦」「！」也會 |
| [`manuscript-check`](skills/manuscript-check/SKILL.md) | 書稿規則式檢查（不用 AI）：Word 稿健檢、定稿與排版 PDF 逐字比對、索引頁碼 | 標點不成對、圖表編號跳號、引用與書目對不上、排版漏段 |

**Hook**（僅 Claude Code）：每次 Write／Edit 寫入新內容後，自動掃簡體字、一簡多繁、錯轉繁，有命中就提醒 Claude 修正。只提醒、不擋寫入；路徑含 `zh-CN`、`zh_Hans`、`zh-SG` 這類簡體在地化標記的檔案自動跳過。

## 安裝

### Claude Code（建議，含 hook）

```
/plugin marketplace add ghostfirewu/zh-tw-writing-skills
/plugin install zh-tw-writing@zh-tw-writing-skills
```

裝好後 skill 以 `/zh-tw-writing:zh-tw-guard` 這類名稱出現，Claude 也會在相關任務自動使用。要暫時關掉 hook，設環境變數 `ZHTW_GUARD_OFF=1`。

**更新與鎖定版本**：
- 自動更新預設關閉。要打開：`/plugin` → Marketplaces → 選 `zh-tw-writing-skills` → Enable auto-update。
- 手動更新：`/plugin marketplace update zh-tw-writing-skills`，或在終端機執行 `claude plugin update zh-tw-writing@zh-tw-writing-skills`。
- 想停在某一版：加入時在後面接標籤，例如 `/plugin marketplace add ghostfirewu/zh-tw-writing-skills#v1.2.0`。
- 每一版改了什麼見 [`CHANGELOG.md`](CHANGELOG.md) 或 GitHub 的 Releases 頁面。

### 其他支援 SKILL.md 的工具（claude.ai、其他 agent）

每個 `skills/<名稱>/` 資料夾都是獨立的 skill，可以單獨取用：複製到該工具的 skills 目錄，或壓成 zip 上傳。腳本需要能執行 Python 的環境；hook 只在 Claude Code 有效。這種裝法沒有自動更新，要自己重新下載或 `git pull`。

### 接進自己的 agent 系統

要讓自己的規則、Lint 或其他 AI 工具讀這裡的詞表與腳本，請看 [`docs/integration.md`](docs/integration.md)：怎麼鎖定版本、哪些檔案格式與參數可以放心依賴、升級時要注意什麼。

## 個人化（不改 plugin 本身）

在自己的專案裡放一個 `.zh-tw-writing/` 資料夾：

| 檔案 | 作用 |
|---|---|
| `terms.tsv` | 追加中國用語，格式同 `skills/zh-tw-guard/data/terms.tsv` |
| `slop.tsv` | 追加 AI 腔詞條，格式同 `skills/zh-tw-anti-slop/data/slop.tsv` |
| `allow.txt` | 白名單，一行一個詞：品牌名、專名、地名，命中落在這些詞裡就不報 |
| `voice.json`、`voice.md` | 個人風格檔，由 `zh-tw-voice` 建立（選用）；內容是個人資料，公開的專案請加進 `.gitignore` |

兩支掃描器和 hook 都會自動讀這個資料夾，掃描結果倒數第二行會註明套用了多少設定（`--json` 不輸出這一行）。細節見 [`docs/integration.md`](docs/integration.md) 第 5 節。

## 需求

- **Python 3.8 以上**。`zh-tw-guard`、`zh-tw-anti-slop`、`zh-tw-voice` 的腳本只用標準函式庫。
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

# 改寫前後比對：抓改寫時多出來或不見的數字、專名、引語，以及語氣強度的變化
python3 skills/zh-tw-anti-slop/scripts/rewrite_diff.py 原文.md 改寫後.md

# 個人口吻：從自己的貼文建風格檔，再拿草稿對照
python3 skills/zh-tw-voice/scripts/voice_profile.py --out .zh-tw-writing/voice.json 貼文*.md
python3 skills/zh-tw-voice/scripts/voice_check.py --register 社群 草稿.md

# 書稿健檢（輸出 Excel 報表）
cd skills/manuscript-check/scripts
python3 稿件健檢.py 書稿.docx
```

掃描器列的都是**候選**。中國用語分兩級：A 級（視頻、軟件）可以直接換；B 級（程序、質量、支持）在台灣也有正常用法，要看語境判斷，對照表寫了每個詞的保留語境。

## 測試

```bash
python3 tests/run_all.py
```

十一組測試：守門掃描器、AI 腔掃描器、改寫前後比對、個人口吻、hook、專案設定、個資檢查、發布一致性、書稿健檢、排版比對、索引頁碼。GitHub Actions 在 Linux、Windows、macOS 上跑。

## 貢獻

歡迎發 PR，詞表是最需要補的部分。流程、詞表規則、版本號，以及哪些內容不能放進公開 repo，都寫在 [`CONTRIBUTING.md`](CONTRIBUTING.md)。

## 授權

- 程式碼：[MIT](LICENSE)
- 規則文字與詞表（`SKILL.md`、`references/`、`data/`、`設定/` 的清單、說明文件）：[CC BY 4.0](LICENSE-CONTENT.md)
- `skills/manuscript-check/scripts/data/筆畫表.tsv`：取自 [Unicode Unihan Database](https://www.unicode.org/charts/unihan.html)，依 Unicode License v3 轉載（授權全文見同資料夾的 `LICENSE-UNICODE.txt`）

## 致謝

中國用語對照表的部分詞條參考了社群整理的支語與 OpenCC 轉換殘留清單（acchuang、voice-guard、aeopress），再逐詞補上台灣語境的保留規則。

`zh-tw-anti-slop` 的判準整理自以下公開資料與 skill 的觀察，依台灣中文的語境重寫，並非逐字轉載：

- 繁中去 AI 腔：acchuang/zh-tw-humanizer、fact-locked-humanizer、humanizer-zh-TW-Pro、speak-human-tw、de-ai-tone
- AI 寫作特徵整理：Wikipedia「Signs of AI writing」、The Field Guide to AI Slop、數位時代〈AI 味〉專文
- 日文去 AI 腔 skill：[nanaism/yomiyasu](https://github.com/nanaism/yomiyasu)（MIT；語意四點、評價保留、擬人的處理範圍、Markdown 粗體失效、改寫前後比對）、[coji/natural-japanese](https://github.com/coji/natural-japanese)（MIT；不一律套用修正、判斷台帳）、[k16shikano 的日本語技術文書規範](https://gist.github.com/k16shikano/fd287c3133457c4fd8f5601d34aa817d)（Unlicense；推測不改斷定、擬人的兩步判準、否定要附理由）
