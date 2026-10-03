# 在這個 repo 裡工作時

這是公開的繁體中文寫作 plugin。開工前先讀 `CONTRIBUTING.md`，規則以它為準。最常出錯的四件事：

1. 要讓使用者拿到的改動，必須升 `.claude-plugin/plugin.json` 的版本號，並更新 `CHANGELOG.md`（那一段會直接變成 GitHub Release 的說明）。
2. 新功能、新詞條先寫會 FAIL 的測試，改完跑 `python3 tests/run_all.py` 全過。
3. 不准放進個人、公司、內部系統的資訊或真實稿件內容；發 PR 前用自己的私人名單搜一遍。
4. 動到 `docs/integration.md` 第 4、5 節的介面時，改名、刪除或改變既有行為才升主版號；新增參數或選用功能只升次版號。
