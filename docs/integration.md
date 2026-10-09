# 接入說明：把這個 repo 接進自己的 agent 系統

> 寫給「不是單純安裝 plugin，而是要把這些 skill 接進自己的規則、Lint、其他 AI 工具」的人。
> 只是在 Claude Code 裡使用的話，照 README 安裝即可，不必讀本檔。

## 1. 三種接法

| 接法 | 適合 | 怎麼升級 |
|---|---|---|
| **Claude Code plugin** | 只用 Claude Code | `/plugin marketplace update zh-tw-writing-skills`，或在 `/plugin` 打開自動更新 |
| **固定版本的副本** | 同時用 Claude Code、Codex 或其他讀 SKILL.md 的工具；自己的規則或 Lint 要讀這裡的詞表 | 用自己的同步腳本換成新標籤的內容（見第 3 節）|
| **Fork 後自行修改** | 要大改、不打算跟上游 | 自己合併上游；授權見 README |

## 2. 想持續升級的話，副本不要直接改

接法二的副本，建議當成**唯讀**：
- 直接改副本，下次升級時改動會被蓋掉，或和新版衝突。
- **要加詞條、白名單**：用專案設定（第 5 節），放在副本外面。
- **發現這裡的錯誤或可以改進的地方**：改在這個 repo（發 PR，見 `CONTRIBUTING.md`），合併後換新標籤，所有接入者都會拿到。

## 3. 同步副本的建議做法

1. **鎖定標籤，不跟 `main`**：例如 `v1.2.0`。`main` 上可能有還沒發布的改動。
2. **記錄鎖定資訊**：標籤、commit、每個檔案的雜湊。之後比對雜湊，就能發現副本有沒有被手改。
3. **升級前先讀 `CHANGELOG.md`**：標「不相容」的條目代表第 4 節的介面變了，自己的 Lint 或腳本可能要跟著改。
4. **升級後跑測試**：`python3 tests/run_all.py`。需要書稿工具包的話，先安裝 `skills/manuscript-check/scripts/requirements.txt`。
5. **只拿需要的部分**：四支 skill 各自獨立，可以只取其中一支（`zh-tw-voice` 和 `zh-tw-anti-slop` 放在同一層時，會順便檢查樣本的 AI 腔密度；沒有也能跑）。`zh-tw-guard` 的 `data/一簡多繁.txt`、`data/錯轉.txt`、`data/台灣正字.txt` 和 `manuscript-check/scripts/設定/` 裡的同名檔是同一份內容，只取書稿工具包時，用的是後者。

## 4. 可以依賴的介面

下列項目（含第 5 節的專案設定）的格式與行為，在同一個主版號內維持相容：改名、刪除或改變既有行為會升主版號，並在 `CHANGELOG.md` 標明；新增參數或選用功能只升次版號。表外的檔案（`references/` 的文字、SKILL.md 的寫法、內部函式）隨時可能調整，不要讓自己的程式解析它們。

### 檔案路徑

| 路徑 | 內容 |
|---|---|
| `skills/<名稱>/SKILL.md` | 四支 skill 的入口：`zh-tw-guard`、`zh-tw-anti-slop`、`zh-tw-voice`、`manuscript-check` |
| `skills/zh-tw-guard/data/terms.tsv` | 中國用語表 |
| `skills/zh-tw-guard/data/一簡多繁.txt`、`錯轉.txt`、`台灣正字.txt` | 字形清單 |
| `skills/zh-tw-anti-slop/data/slop.tsv` | AI 腔詞條 |
| `skills/*/scripts/*.py` | 掃描腳本（參數見下）|
| `hooks/hooks.json`、`hooks/run.sh`、`hooks/zhtw_post_write.py` | 寫檔後的簡體提醒（`hooks.json` 透過 `run.sh` 找 Python 執行 `zhtw_post_write.py`）|

### 資料格式（UTF-8，`#` 開頭為註解）

| 檔案 | 欄位（Tab 分隔）|
|---|---|
| `terms.tsv` | 詞、建議、級別（`A`＝直接換，`B`＝看語境）、排除詞（`\|` 分隔，可空）、說明（可空）|
| `slop.tsv` | 樣式（`re:` 開頭為正規表示式，否則照字面）、類別、改寫方向 |
| `一簡多繁.txt` | 逗號分隔：字、可疑二字組（`\|` 分隔）、排除詞（`\|` 分隔，可省略）；`'` 開頭為註解 |
| `錯轉.txt` | 一行一個詞；`'` 開頭為註解 |
| `台灣正字.txt` | 一行一個字，Tab 後可加說明；`'` 開頭為註解。列出的字不算簡體字（標準 Big5 沒收、但台灣正式使用，例：酶、肽）|

> **詞表的增刪都算次版號**（包括新增、刪除詞條，以及把詞條改成 A 級或 B 級），不是不相容變更；但你的 Lint 可能多出或少了命中，改級別還會改變 `zhtw_check.py` 的結束代碼。升級時留意 `CHANGELOG.md` 的「詞表」段，影響結束代碼的會另外註明。

### 腳本參數與結束代碼

| 腳本 | 參數 | 結束代碼 |
|---|---|---|
| `zhtw_check.py` | 檔案（`-`＝標準輸入）、`--only`（逗號分隔：簡體、一簡多繁、錯轉、用語）、`--level A\|B\|all`、`--json`、`--config-dir`、`--no-config` | 有簡體、一簡多繁、錯轉或 A 級用語＝1；只有 B 級或沒有命中＝0；用法錯誤＝2 |
| `slop_scan.py` | 檔案（`-`＝標準輸入）、`--json`、`--summary`、`--config-dir`、`--no-config` | 有命中＝1；沒有＝0；用法錯誤＝2 |
| `rewrite_diff.py` | 原文、改寫後、`--json` | 有任何增減＝1；沒有＝0；用法錯誤＝2 |
| `voice_profile.py` | 樣本檔（可多個，`-`＝標準輸入）、`--json`、`--out`、`--phrase`（可重複）、`--split` | 成功＝0；用法錯誤或讀不到檔案＝2 |
| `voice_check.py` | 草稿（`-`＝標準輸入）、`--register 社群\|正式`（必填）、`--profile`、`--config-dir`、`--json` | 有超出或長句＝1；沒有＝0；用法錯誤、社群模式找不到風格檔＝2 |
| `manuscript-check` 三支 | 見 `skills/manuscript-check/SKILL.md`；`--設定` 可指向自己的設定檔 | 照各工具說明 |

`--json` 的輸出欄位，在同一個主版號內只會新增，不會改名或刪除。

### Hook 行為

- 掛在 Claude Code 的 `PostToolUse`（`Write|Edit|MultiEdit`）。
- 只檢查這次寫入的新內容，抓簡體、一簡多繁、錯轉三類。
- 有命中時結束代碼 2，訊息寫到 stderr（提醒 Claude，不擋寫入）。
- 路徑含 `zh-CN`、`zh_CN`、`zhcn`、`zh-Hans`、`zh-SG`、`zh-MY` 的檔案跳過（不分大小寫）；`ZHTW_GUARD_OFF=1` 可整個關閉。
- 讀專案設定的白名單（第 5 節）。
- 用副本接入時，自己在 `settings.json` 指向副本的 `hooks/zhtw_post_write.py`；不要同時安裝 plugin，否則會重複提醒。

## 5. 專案設定：不改副本也能個人化

在專案裡放一個 `.zh-tw-writing/` 資料夾：

| 檔案 | 作用 | 讀取者 |
|---|---|---|
| `terms.tsv` | 追加中國用語；和內建同一個詞時，以這裡為準 | `zhtw_check.py` |
| `slop.tsv` | 追加 AI 腔詞條；比對時排在內建詞條之前，和內建同一個樣式時以這裡為準 | `slop_scan.py` |
| `allow.txt` | 白名單，一行一個詞；命中落在這些詞裡就不報（品牌名、專名、地名、引文）| 兩支掃描器與 hook |
| `voice.json` | 個人風格的統計值，由 `voice_profile.py --out` 產生；欄位見下 | `voice_check.py` |
| `voice.md` | 個人風格的質性描述與分類（`身分`／`語域:社群`／`缺陷`），格式見 `skills/zh-tw-voice/references/voice-template.md` | agent（`zh-tw-voice`），腳本不解析 |

- **找資料夾的順序**：`--config-dir` → 環境變數 `ZHTW_WRITING_DIR` → `$CLAUDE_PROJECT_DIR/.zh-tw-writing` → 目前目錄的 `.zh-tw-writing`。**不往上層資料夾找**，在專案的子資料夾裡執行時，請用環境變數或 `--config-dir`。`--config-dir` 指到不存在的路徑時，結束代碼 2；環境變數 `ZHTW_WRITING_DIR` 指到不存在的路徑時不報錯，直接改找下一順位。
- 三個檔案都是 UTF-8，`#` 或 `'` 開頭的行是註解。
- 白名單的比對方式：命中的文字整段落在白名單某個詞的某次出現之內，就不報。白名單有「一站式學習平台」時，同一行單獨出現的「一站式」照報。
- 掃描器的輸出倒數第二行會寫「套用專案設定…（本次略過 N 筆）」，讓人知道白名單藏掉了多少命中（`--json` 不輸出這一行）。
- **白名單只放確定的專名**：寫太寬（例如放「一站式」三個字），會連真正的 AI 腔一起藏掉。
- 設定檔格式錯誤的列（`terms.tsv` 級別不是 A／B、`slop.tsv` 缺類別欄、正規式寫錯、含無法解碼的字元）會被略過，不會讓工具中斷。
- `voice.json` 的欄位：`版本`、`樣本`（篇數、字數、信心）、`句長`（p25、中位數、p75）、`段落長`、`每千字`（語氣詞、驚嘆號、問號、刪節號、破折號、波浪號、emoji、網路用語、英文詞；網址不算字數）、`語氣詞`、`自稱`、`口頭禪`、`長句上限`、`樣本明細`（檔名、字數、AI腔每千字、疑似AI腔）。同一個主版號內只新增欄位。使用者可以手改「長句上限」和「口頭禪」。
- `voice.json`、`voice.md` 是個人資料：專案是公開 repo 時，請加進 `.gitignore`。`voice.json` 只存統計值和檔名，不存原文。
- 書稿工具包不讀這個資料夾，改用它自己的 `--設定` 參數指向另一份 `設定.ini`。
