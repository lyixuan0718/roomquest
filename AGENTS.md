# AGENTS.md — RoomQuest 程式 repo 協作規則

## 專案目的
RoomQuest 的可執行程式：場景資料 → AI 出題 → Python 驗證 → 主持人核准 → 玩家遊玩。
設計說明放在 roomquest-project-hub 與 roomquest-agent-wiki，這個 repo 只放程式、資料與紀錄。

## 不能違反的規則
1. **verifier 是唯一的關卡把關點。** 任何 game.json 都必須通過 `roomquest.verifier.verify()` 才能給玩家；不得為了讓測試通過而放寬規則。
2. **玩家端不呼叫 AI，也不把答案送到瀏覽器。** `play.view()` 不得包含未解出的答案；修改介面後要跑 `tests/test_play.py`。
3. **程式不替模型補資料。** 格式或內容不合規就回報錯誤碼與原因，不自行猜測欄位。
4. **只使用主持人確認的物品**（`confirmed: true`）。`dynamic: true` 的物品不能當答案來源。
5. **紀錄必須真實。** `logs/` 只放實際執行或遊玩產生的檔案；不得捏造人數、時間、通過率。
6. **狀態誠實標示**：場景與遊戲的 `status` 只能是「示意案例」「測試中」「已驗證」；「已驗證」必須有對應的 `logs/plays/` 紀錄。

## 檔案結構
```
roomquest/normalize.py   答案正規化
roomquest/verifier.py    規則驗證與錯誤碼
roomquest/play.py        玩家端遊戲邏輯（不含介面）
roomquest/player_ui.py   Gradio 玩家介面
app_player.py            啟動玩家模式
data/scenes/<scene_id>/  scene.json + game.json
tests/                   pytest
notebooks/               Colab 入口（課程格式，一格一格附說明）
logs/plays/              遊玩紀錄 JSONL
```

## 新增場景
1. 建立 `data/scenes/<scene_id>/`，`scene_id` 使用小寫英文與連字號。
2. scene.json 的物品只寫實際觀察或主持人確認的內容；不確定就 `confirmed: false`。
3. 寫 game.json 後執行 `python -m roomquest.verifier <scene.json> <game.json>`，錯誤必須為 0。
4. 在 `tests/` 加入至少一個「改壞一處就會失敗」的測試。

## 新增驗證規則
- 每條規則有固定錯誤碼、中文訊息（說明原因與修改方向）與 `step`。
- 會擋下關卡的用 `error`；需要人判斷的用 `warning`。
- 同時新增測試與 README 錯誤碼表。

## 完成前檢查
```bash
python -m pytest -q
python -m roomquest.verifier data/scenes/<scene_id>/scene.json data/scenes/<scene_id>/game.json
python app_player.py --scene-dir data/scenes/<scene_id>   # 手機寬度實際玩到最終密碼
```
