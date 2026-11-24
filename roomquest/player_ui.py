"""Gradio 玩家介面。答案只存在伺服器端；瀏覽器只收到目前要顯示的文字。"""

from __future__ import annotations

from pathlib import Path

import gradio as gr

from .play import PlayLogger, load_approved_game, new_state, reveal_hint, submit, view


def _render(game: dict, state: dict, feedback: str = ""):
    v = view(game, state)
    collected = "、".join(v["collected"]) if v["collected"] else "（還沒有）"
    if v["phase"] == "level":
        progress = f"**第 {v['step']} / {v['total']} 關**｜已取得：{collected}"
        clue = f"### 線索\n\n{v['clue']}"
    elif v["phase"] == "final":
        progress = f"**最後一步**｜已取得：{collected}"
        clue = f"### 最終密碼\n\n{v['clue']}"
    else:
        minutes, seconds = divmod(v["elapsed"], 60)
        progress = "**挑戰完成**"
        clue = (f"## 你解開了「{v['title']}」\n\n最終密碼：**{game['final_code']}**\n\n"
                f"用時 {minutes} 分 {seconds} 秒｜打開提示 {v['hint_total']} 次｜答錯 {v['wrong_total']} 次")
    hints = "\n".join(f"{i}. {h}" for i, h in enumerate(v["hints"], start=1))
    hints_md = f"**提示**\n\n{hints}" if hints else ""
    playing = v["phase"] in ("level", "final")
    hint_label = f"顯示下一層提示（剩 {v['hints_left']} 則）" if v["hints_left"] else "沒有更多提示了"
    return (
        state,
        progress,
        clue,
        hints_md,
        feedback,
        gr.update(value="", visible=playing, label="最終密碼" if v["phase"] == "final" else "你的答案"),
        gr.update(visible=playing),
        gr.update(visible=v["phase"] == "level", interactive=v["hints_left"] > 0, value=hint_label),
    )


def build_player_app(scene_path: str | Path, game_path: str | Path,
                     log_dir: str | Path | None = "logs/plays") -> gr.Blocks:
    game = load_approved_game(scene_path, game_path)  # 未通過驗證的遊戲會在這裡被拒絕
    logger = PlayLogger(Path(log_dir) if log_dir else None)

    def start():
        state = new_state()
        logger.write(game, state, "start")
        return _render(game, state)

    def on_submit(state, text):
        state, message, _ = submit(game, state, text, logger)
        return _render(game, state, message)

    def on_hint(state):
        return _render(game, reveal_hint(game, state, logger))

    with gr.Blocks(title=f"RoomQuest｜{game['title']}") as demo:
        gr.Markdown(f"# {game['title']}\n\n{game.get('story', '')}")
        state = gr.State()
        progress = gr.Markdown()
        clue = gr.Markdown()
        answer = gr.Textbox(label="你的答案", placeholder="輸入數字或短詞，按 Enter 送出")
        with gr.Row():
            submit_btn = gr.Button("確認答案", variant="primary")
            hint_btn = gr.Button("顯示下一層提示")
        feedback = gr.Markdown()
        hints = gr.Markdown()
        restart_btn = gr.Button("重新開始", size="sm")
        gr.Markdown("<small>玩家模式只讀取主持人核准、且通過 Python 驗證的遊戲資料；遊玩時不呼叫 AI。</small>")

        outputs = [state, progress, clue, hints, feedback, answer, submit_btn, hint_btn]
        demo.load(start, outputs=outputs)
        submit_btn.click(on_submit, inputs=[state, answer], outputs=outputs)
        answer.submit(on_submit, inputs=[state, answer], outputs=outputs)
        hint_btn.click(on_hint, inputs=[state], outputs=outputs)
        restart_btn.click(start, outputs=outputs)
    return demo
