"""啟動 RoomQuest 玩家模式。

    python app_player.py                                   # 預設載入 B305 示意案例
    python app_player.py --scene-dir data/scenes/<場景> --share
"""

import argparse
from pathlib import Path

from roomquest.player_ui import build_player_app

parser = argparse.ArgumentParser(description="RoomQuest 玩家模式")
parser.add_argument("--scene-dir", default="data/scenes/classroom-b305", help="包含 scene.json 與 game.json 的資料夾")
parser.add_argument("--log-dir", default="logs/plays", help="遊玩紀錄 JSONL 的存放位置")
parser.add_argument("--port", type=int, default=7860)
parser.add_argument("--share", action="store_true", help="產生 Gradio 公開連結（約一週後失效）")
args = parser.parse_args()

scene_dir = Path(args.scene_dir)
demo = build_player_app(scene_dir / "scene.json", scene_dir / "game.json", args.log_dir)
demo.launch(server_port=args.port, share=args.share)
