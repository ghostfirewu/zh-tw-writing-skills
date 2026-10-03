# 變更紀錄

版本規則（主版號.次版號.修訂號）：
- **主版號**：`docs/integration.md` 第 4、5 節的介面有不相容變更——改名、刪除或改變既有行為才升主版號；新增參數或選用功能只升次版號。
- **次版號**：新增功能、新增參數、新增或刪除詞條、調整詞條級別（A／B）。詞表的變動不算不相容，但接入者的 Lint 可能多出或少了命中；調整級別還會改變 `zhtw_check.py` 的結束代碼。這些都列在「詞表」段，影響結束代碼的另外註明。
- **修訂號**：修正錯誤、調整文字，不改介面也不增減詞條。

每次發布都要升 `.claude-plugin/plugin.json` 的版本號。CI 通過後會自動建立 `v<版本號>` 標籤與 GitHub Release（說明取自本檔對應的段落），Claude Code 使用者也只有在版本號改變時才會收到更新。

## v1.3.0

**新增**
- `zh-tw-guard/references/char-variants.md`：一簡多繁、錯轉命中後該改成哪個正體的分工對照（后／後、里／裡、干／乾／幹……共 17 字），附殘留例與錯轉例。`SKILL.md` 加了指路。
- `protect.md`「應放行」新增「單點徵兆」：單獨出現的轉場詞、破折號、四字格多半是正常書寫，同一段同類徵兆聚集（短段 2 處、長段 3 處以上）才算 AI 痕跡；禁用詞句不在此列。

**變更**
- `protect.md`「合法詞換合法詞」補例：「項目」指清單的一項是台灣正常用法，指計畫才改「專案」。
- `patterns.md`「模糊歸因」的假精確擴為三種：精確到小數點的數字之外，加上點不開的連結、查無此物的研究或報告名稱。
- `patterns.md`「文風斷層」的不觸發補一類：作者自己交代要換語氣的段落（章末寫給讀者的信、插入的日記）。
- `patterns.md`「AI 工具標記殘留」補 `attached_file`；不觸發補「技術文件裡被當成引用對象的識別碼」。

**詞表**（修正跨詞誤判，兩者都會讓命中變少）
- `slop.tsv`：「好問題」改為正規式，不再命中「偏好問題」（偏好＋問題）。
- `terms.tsv`：「構建」加排除詞「架構建」，不再命中「架構建議」（架構＋建議）。⚠️ 「構建」是 A 級，原本會讓 `zhtw_check.py` 結束代碼為 1 的「架構建議」，現在不再觸發。

## v1.2.2

**修正**
- `hooks/run.sh`：改成實際執行一次確認 Python 能用才採用，依序試 `python3`、`python`。過去只看 `command -v` 找不找得到，Windows 上的 Microsoft Store 空殼別名找得到卻跑不動，每次寫檔都會跳出錯誤；現在會改用下一個，都不能用就安靜放行。探測時不讀標準輸入，不影響交給 hook 的內容。
- `hooks/zhtw_post_write.py` 剝除前置 BOM 的那行，原本直接寫了看不見的 U+FEFF 字元，改成轉義寫法 `\uFEFF`。行為不變，只是編輯器和 diff 終於看得到它。`tests/test_hook.py` 同一處一併改。

**新增**
- `tests/test_hook.py`：`run.sh` 三種情況的測試（python3 是空殼、兩個都是空殼、python3 正常）；系統沒有 `sh` 時略過。
- `tests/test_meta.py`：文字檔中段不得含字面 BOM。

**詞表**：無變動。

## v1.2.1

**新增**
- 自動發布：`main` 上的測試通過後，除了建立標籤，也會建立 GitHub Release，說明取自 `CHANGELOG.md` 對應版本的段落。
- 舊版標籤可以在 Actions 頁面手動執行 `release`、輸入版本號，補建 Release。
- `tests/test_meta.py` 檢查 `CHANGELOG.md` 有目前版本的說明段落。

**詞表**：無變動。

## v1.2.0

**新增**
- 專案設定 `.zh-tw-writing/`：`terms.tsv`、`slop.tsv` 追加詞條，`allow.txt` 白名單；兩支掃描器與 hook 都會讀。新參數 `--config-dir`、`--no-config`。
- `docs/integration.md`：接入說明與穩定介面清單。
- `CONTRIBUTING.md`：維護規則；`.claude/CLAUDE.md` 指向它。
- 個資檢查 `tests/test_privacy.py`：Windows 絕對路徑與網路路徑、個人家目錄路徑、email、Office 與 PDF 檔的作者、公司及帳號欄位。
- 發布一致性檢查 `tests/test_meta.py`：`CHANGELOG.md` 最上面的版本要等於 `plugin.json` 的版本。
- 自動打標籤：`main` 上的測試通過後，依 `plugin.json` 版本號建立標籤。
- `AGENTS.md`：讓 Codex 等讀 `AGENTS.md` 的工具也看得到維護規則。
- README：補「更新與鎖定版本」「個人化」兩段。

**修正**
- `manuscript-check` 三支腳本的說明範例，改用相對路徑。

**詞表**：無變動。

## v1.1.0

**新增**
- `zh-tw-anti-slop/references/rewrite-safety.md`：語意四點、強度兩個方向都不動、改寫產物自檢、不一律套用修正、判斷台帳、雙向自審。
- `references/patterns.md`：翻譯腔、AI 慣性、擬人（兩步判準）、版面與格式。
- `references/protect.md`：五類硬保護、應放行的情況、提及與使用。
- `scripts/rewrite_diff.py`：比對改寫前後的數字、英文詞、引語與語氣用語增減。
- `slop_scan.py`：Markdown 粗體失效偵測。

**變更**
- `rules.md`：墊片詞若在下評價，改成把評價移到句子後半；二元對比改用稻草人與遞進兩個測試判斷是否保留；書稿全檔只標注。
- `SKILL.md` 流程改為由深到淺，加入分配、判斷台帳、改寫前後比對三步。

**詞表**（`slop.tsv`）：新增擬人、句尾綴掛評論、模糊歸因、框式介詞、英式句框、冗餘量詞、強制昇華結尾、意義膨脹、AI 工具標記等詞條；墊片詞與二元對比的改寫方向更新。

## v1.0.0

首次發布：`zh-tw-guard`、`zh-tw-anti-slop`、`manuscript-check` 三支 skill，以及寫檔後提醒簡體殘留的 hook。
