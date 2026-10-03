# 參與維護

歡迎任何人發 PR，人類或 AI agent 都一樣。這份規則也是寫給在這個 repo 裡工作的 AI agent 的：開工前請讀完。

## 流程

1. 開分支、改動、發 PR；不直接推 `main`。
2. 跑 `python3 tests/run_all.py`，全部 `PASS` 才發 PR（書稿工具包的測試需要先安裝 `skills/manuscript-check/scripts/requirements.txt`）。
3. 要讓使用者拿到的改動，**一定要升 `.claude-plugin/plugin.json` 的版本號**，並在 `CHANGELOG.md` 最上面寫一段。版本規則見 `CHANGELOG.md` 開頭。
   - 沒升版本號，Claude Code 使用者就算打開自動更新也收不到。
   - 合併後 CI 會自動建立 `v<版本號>` 標籤和 GitHub Release，Release 說明直接取自 `CHANGELOG.md` 那一段，所以那一段要寫給使用者看。不必手動打標籤。
4. 動到 `docs/integration.md` 第 4、5 節列出的介面（檔案路徑、資料格式、參數、結束代碼、`--json` 欄位、hook 行為、專案設定）：**改名、刪除或改變既有行為才升主版號；新增參數或選用功能只升次版號**。詞表增刪、改 A／B 級別不算這裡的「刪除」，一律升次版號（見 `CHANGELOG.md` 開頭）。升主版號時在 `CHANGELOG.md` 標明「不相容」。
5. 改到 `skills/manuscript-check/` 時，除了 `CHANGELOG.md`，也要在 `skills/manuscript-check/scripts/變更紀錄.md` 最後追加一筆（那份隨工具包單獨流通）。

## 詞表

- **中國用語**：`skills/zh-tw-guard/data/terms.tsv` 加一列，同時把同一個詞補進 `references/terms.md` 對應的表（測試會比對兩邊）。
  - B 級（看語境）詞一定要寫保留語境，能列排除詞就列。
  - 加詞前先想：這個詞在台灣有沒有正常用法？有就是 B 級，或乾脆不收。例：「土豆」在台灣多指花生。
- **一簡多繁、錯轉**：改 `skills/zh-tw-guard/data/` 的清單時，`skills/manuscript-check/scripts/設定/` 的同名檔要一起改（測試會比對兩份）。
- **AI 腔**：`skills/zh-tw-anti-slop/data/slop.tsv`。
  - 字面義、慣用語不收，例如「落地窗」「歷史告訴我們」。判斷方法：AI 普及以前的人類文章也常見，就不要收。
  - 新詞條在 `tests/test_slop_scan.py` 補一條會命中、一條不該命中的測試。
- 新功能、新詞條都要**先寫會 FAIL 的測試**，確認測試真的抓得到，再改到 PASS。

## 規則文字（SKILL.md、references/）

- 判準要附具體例子；一個抽象詞沒有例子，等於沒寫完。最好舉兩個長得不一樣的例子。
- 「改寫成具體事實」的指示，一律限原文已有的事實，不准要求替作者補數字、案例、立場或理由。
- 檔案之間的引用（「見 X 第 N 節」）要指得到。改章節編號時，搜一下有沒有別處引用。
- 說明文字本身要過自己的檢查：
  ```bash
  python3 skills/zh-tw-guard/scripts/zhtw_check.py --only 簡體,一簡多繁,錯轉 檔案.md
  python3 skills/zh-tw-anti-slop/scripts/slop_scan.py 檔案.md
  ```
  命中如果是刻意舉的例子就沒關係。

## 不准放進來的東西

這個 repo 是公開的。從自己的部署帶改動過來時，最容易夾帶這些：

- 個人或公司資訊：姓名、email、帳號、公司或出版社名稱、客戶名稱。
- 內部資訊：本機路徑、內部系統或 agent 的名稱、內部規則的條號、專案代號。
- 真實稿件的內容：例句要自己改寫或虛構，不要直接貼工作上的稿子。
- 測試用的 Word、PDF 檔：作者欄要清成 `Author`，不能留帳號資訊。

`tests/test_privacy.py` 會在 CI 檢查通用格式（Windows 絕對路徑、email、Office 與 PDF 的作者欄）。**具體名稱它抓不到**，因為那份名單本身也會公開。發 PR 前，請用自己手邊的私人名單搜一遍改動內容，例如：

```bash
git diff origin/main --name-only | xargs grep -n -f ~/my-private-names.txt
```

這份私人名單放在 repo 外面，不要 commit。

commit 的作者 email 也會公開。建議在 GitHub 的 email 設定打開「Keep my email addresses private」，用 GitHub 提供的 noreply 地址 commit。
