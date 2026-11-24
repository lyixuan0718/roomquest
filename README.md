# RoomQuest

把真實空間照片變成可以在現場完成的解謎遊戲。核心原則：**AI 出題、程式驗題、人最後核准**。

- 課程：生成式 AI（期末專案，個人製作）
- 作者：B1228010 長庚 AI 四 李怡萱
- 設計筆記：[roomquest-project-hub](https://lyixuan0718.github.io/roomquest-project-hub/)・[roomquest-agent-wiki](https://lyixuan0718.github.io/roomquest-agent-wiki/)

## 目前進度

| 元件 | 狀態 | 說明 |
|---|---|---|
| scene.json / game.json 格式 | 完成 | 沿用 Agent Wiki W02，增加 `movable` 與 `references` |
| `roomquest/verifier.py` | 完成 | 規則驗證，不呼叫 AI；有測試案例 |
| `roomquest/play.py` + 玩家介面 | 完成 | Gradio；答案只留在伺服器端；記錄遊玩事件 |
| 真實教室場景 | 進行中 | 目前只有 B305 **示意案例**，尚未實際遊玩 |
| `planner.py`（AI 出題） | 未開始 | AISuite + 兩階段規劃 + Reflection |
| `parser.py`（照片解析） | 未開始 | 視覺模型；失敗時改由主持人手動輸入 |
| 主持人介面 | 未開始 | 編輯場景、生成、驗證報告、核准匯出 |

## 快速開始

```bash
pip install -r requirements.txt
python -m pytest -q                                    # 執行所有測試
python -m roomquest.verifier data/scenes/classroom-b305/scene.json data/scenes/classroom-b305/game.json
python app_player.py                                   # http://127.0.0.1:7860
python app_player.py --share                           # 產生公開連結（約一週後失效）
```

Colab：開啟 `notebooks/RoomQuest_01_verifier_player.ipynb`，從上到下執行。

## 資料格式

每個場景一個資料夾：`data/scenes/<scene_id>/scene.json` 與 `game.json`。

**scene.json 物品欄位**

| 欄位 | 說明 |
|---|---|
| `id`, `name`, `category`, `use[]`, `color`, `region`, `count`, `text` | 可被線索條件比對的屬性 |
| `attributes{}` | 其他可當答案的屬性，例如 `paper_count`、`cover_number` |
| `relations[]` | `{type: on/in/under/next_to, object: <id>}` |
| `touchable` | 玩家能否碰觸 |
| `movable` | 位置可能被移動（驗證器會提醒開場前確認） |
| `dynamic` | 內容會隨時間改變（時鐘、螢幕），**不能當答案** |
| `confirmed` | 主持人是否已確認；未確認的物品不能出題 |

**game.json 關卡欄位**

| 欄位 | 說明 |
|---|---|
| `clue`, `hints[1–3]` | 玩家看到的線索與分層提示 |
| `references[]` | 線索依序指向的物品與條件；每一個都必須在場景中**唯一** |
| `constraints` 的 `"$step1"` | 使用第 1 關答案當條件，驗證器會檢查依賴順序與數值 |
| `actions[]` | `observe` / `count` / `read`；`touch` / `open` 需物品 `touchable` |
| `answer`, `answer_type` | `number` / `choice` / `short_text` |
| `answer_source` | 答案從哪個物品的哪個欄位算出來；`transform`：`identity` / `last_digit` / `digits` |
| `final_code`, `final_code_from[]` | 最終密碼必須等於指定關卡答案依序組合 |

## 驗證器錯誤碼

錯誤（error）會擋下關卡；警告（warning）交給主持人判斷。

| 錯誤碼 | 等級 | 意思 |
|---|---|---|
| `SCHEMA_ERROR` | error | 欄位缺少、型別錯誤、提示數量不對 |
| `UNKNOWN_OBJECT` / `UNCONFIRMED_OBJECT` | error | 引用不存在或未經確認的物品 |
| `AMBIGUOUS_TARGET` | error | 條件同時符合多個物品 |
| `NO_MATCH` / `WRONG_TARGET` | error | 條件找不到物品，或指到別的物品 |
| `BAD_DEPENDENCY` | error | 使用尚未取得的答案、關卡編號不連續 |
| `DYNAMIC_ANSWER` | error | 答案來自會變動的物品 |
| `ANSWER_MISMATCH` / `ANSWER_SOURCE_INVALID` | error | 答案無法由場景資料算出 |
| `ANSWER_SOURCE_NOT_REFERENCED` | error | 線索沒有帶玩家找到答案所在的物品 |
| `UNSAFE_ACTION` | error | 動作不在白名單、碰觸不可碰或危險物品 |
| `FINAL_CODE_MISMATCH` | error | 最終密碼和各關答案組合不一致 |
| `MOVABLE_OBJECT` | warning | 物品可能被移動，開場前確認 |
| `NAME_LEAK` / `ANSWER_IN_CLUE` | warning | 線索直接寫出物品名稱或答案 |

**限制**：唯一性只涵蓋主持人已確認的物品。照片沒拍到的相似物品、玩家對文字的不同理解，仍需要主持人在現場確認。

## 遊玩紀錄

玩家端每個動作寫一行到 `logs/plays/<game_id>.jsonl`（作答、提示、完成時間）。這些是期末報告的數據來源；只放真實遊玩的紀錄，不手動補資料。
